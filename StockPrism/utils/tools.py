import concurrent.futures
import os
import time
import urllib.parse
import requests
import yfinance as yf
from langchain.tools import tool
from StockPrism.utils.logger import get_logger

logger = get_logger("Tools")

# Configurable timeout for external network/yfinance calls (defaults to 6.0 seconds)
DEFAULT_TOOL_TIMEOUT = float(os.getenv("TOOL_TIMEOUT_SECONDS", "6.0"))

# Shared thread pool executor with daemon workers to ensure non-blocking timeouts
_TOOL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=10,
    thread_name_prefix="StockPrism-ToolWorker",
)

# User agent header to prevent Yahoo Finance blocking queries with 403 Forbidden
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _run_with_timeout(func, *args, timeout: float = DEFAULT_TOOL_TIMEOUT, **kwargs):
    """Run a callable in the shared thread pool with a strict timeout limit."""
    future = _TOOL_EXECUTOR.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        raise TimeoutError(f"Operation timed out after {timeout:.1f}s")


def _fetch_ticker_attr(ticker: str, attr_name: str, timeout: float = DEFAULT_TOOL_TIMEOUT):
    """Safely fetch an attribute from a yfinance Ticker with a timeout."""
    def _fetch():
        stock = yf.Ticker(ticker)
        return getattr(stock, attr_name, None)

    return _run_with_timeout(_fetch, timeout=timeout)


def _safe_df_to_dict(df, empty_message: str):
    """Safely convert a pandas DataFrame or Series to a serializable dict."""
    if df is None:
        return empty_message
    if hasattr(df, "empty") and df.empty:
        return empty_message

    try:
        data = df.copy()
        if hasattr(data, "columns"):
            data.columns = [
                c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c)
                for c in data.columns
            ]
        if hasattr(data, "index"):
            data.index = [
                i.strftime("%Y-%m-%d") if hasattr(i, "strftime") else str(i)
                for i in data.index
            ]
        result = data.to_dict()
        return result if result else empty_message
    except Exception as exc:
        logger.warning(f"Could not convert data to dictionary: {exc}")
        return empty_message


# --------------------------------------------------------------------------------
# Tool 1: Retrieve Company Stock Price
# --------------------------------------------------------------------------------
@tool("get_stock_price", description="A function that returns the current stock price of a given ticker")
def get_stock_price(ticker: str):
    logger.info(f"Retrieving Stock Price of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()

    def _fetch_price():
        stock = yf.Ticker(ticker)
        # Fast path via fast_info (avoids downloading huge full info dict)
        price = None
        try:
            fast_info = getattr(stock, "fast_info", None)
            if fast_info:
                price = getattr(fast_info, "last_price", None) or getattr(fast_info, "lastPrice", None)
        except Exception:
            price = None

        # Fallback to stock.info if fast_info is unavailable
        if price is None:
            info = stock.info or {}
            price = (
                info.get("regularMarketPrice")
                or info.get("currentPrice")
                or info.get("previousClose")
                or info.get("ask")
                or info.get("bid")
            )
        return price

    try:
        stock_price = _run_with_timeout(_fetch_price, timeout=DEFAULT_TOOL_TIMEOUT)
        end_time = time.time()

        if stock_price is None:
            return f"No price data available for {ticker}"

        logger.info(f"Retrieved Stock Price of {ticker} in {end_time - start_time:.3f} seconds")
        return stock_price

    except TimeoutError:
        logger.warning(f"Stock price lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Stock price lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve stock price of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve stock price for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 2: Retrieve Company Stock Historical Data
# --------------------------------------------------------------------------------
@tool("get_historical_data", description="A function that returns the historical data of a given ticker in the given start and end date")
def get_historical_data(ticker: str, start_date: str, end_date: str):
    logger.info(f"Retrieving Historical Data of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        def _fetch_hist():
            stock = yf.Ticker(ticker)
            return stock.history(start=start_date, end=end_date)

        history_df = _run_with_timeout(_fetch_hist, timeout=DEFAULT_TOOL_TIMEOUT)
        historical_data = _safe_df_to_dict(
            history_df,
            f"No historical data available for {ticker} between {start_date} and {end_date}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Historical Data of {ticker} in {end_time - start_time:.3f} seconds")
        return historical_data

    except TimeoutError:
        logger.warning(f"Historical data lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Historical data lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve historical data of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve historical data for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 3: Retrieve Company Stock News
# --------------------------------------------------------------------------------
@tool("get_stock_news", description="A function that returns the news of a given ticker")
def get_stock_news(ticker: str):
    logger.info(f"Retrieving News of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        def _fetch_news():
            stock = yf.Ticker(ticker)
            return stock.news

        news = _run_with_timeout(_fetch_news, timeout=DEFAULT_TOOL_TIMEOUT)

        if not news:
            return f"No news available for {ticker}"

        # Compact news to the 4 most recent headlines to conserve token budget
        compact_news = []
        for item in news[:4]:
            if not isinstance(item, dict):
                continue
            content = item.get("content", {}) if isinstance(item.get("content"), dict) else item
            title = content.get("title") or item.get("title")
            if not title:
                continue
            compact_news.append({
                "title": title,
                "publisher": content.get("publisher") or item.get("publisher") or "Unknown",
                "link": (
                    content.get("canonicalUrl", {}).get("url")
                    if isinstance(content.get("canonicalUrl"), dict)
                    else item.get("link")
                ),
            })

        end_time = time.time()
        logger.info(f"Retrieved News of {ticker} in {end_time - start_time:.3f} seconds")
        return compact_news if compact_news else f"No news available for {ticker}"

    except TimeoutError:
        logger.warning(f"News lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"No news available for {ticker} (lookup timed out after {DEFAULT_TOOL_TIMEOUT:.0f}s)"
    except Exception as e:
        logger.error(f"Failed to retrieve news of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve news for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 4: Retrieve Company's Balance Sheet
# --------------------------------------------------------------------------------
@tool("get_balance_sheet", description="A function that returns the balance sheet of a given ticker")
def get_balance_sheet(ticker: str):
    logger.info(f"Retrieving Balance Sheet of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "balance_sheet")
        balance_sheet = _safe_df_to_dict(
            raw_data,
            f"No balance sheet available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Balance Sheet of {ticker} in {end_time - start_time:.3f} seconds")
        return balance_sheet

    except TimeoutError:
        logger.warning(f"Balance sheet lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Balance sheet lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve balance sheet of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve balance sheet for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 5: Retrieve Company's Income Statement
# --------------------------------------------------------------------------------
@tool("get_income_statement", description="A function that returns the income statement of a given ticker")
def get_income_statement(ticker: str):
    logger.info(f"Retrieving Income Statement of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "financials")
        income_statement = _safe_df_to_dict(
            raw_data,
            f"No income statement available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Income Statement of {ticker} in {end_time - start_time:.3f} seconds")
        return income_statement

    except TimeoutError:
        logger.warning(f"Income statement lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Income statement lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve income statement of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve income statement for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 6: Retrieve Company's Cash Flow Statement
# --------------------------------------------------------------------------------
@tool("get_cash_flow", description="A function that returns the cash flow statement of a given ticker")
def get_cash_flow(ticker: str):
    logger.info(f"Retrieving Cash Flow of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "cashflow")
        cash_flow = _safe_df_to_dict(
            raw_data,
            f"No cash flow available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Cash Flow of {ticker} in {end_time - start_time:.3f} seconds")
        return cash_flow

    except TimeoutError:
        logger.warning(f"Cash flow lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Cash flow lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve cash flow of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve cash flow for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 7: Retrieve Company Info & Ratios
# --------------------------------------------------------------------------------
@tool("get_company_info", description="A function that returns company profile and key financial ratios")
def get_company_info(ticker: str):
    logger.info(f"Retrieving Company Info of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        def _fetch_info():
            stock = yf.Ticker(ticker)
            return stock.info

        info = _run_with_timeout(_fetch_info, timeout=DEFAULT_TOOL_TIMEOUT)

        if not info:
            return f"No company info available for {ticker}"

        # Prune 100+ raw fields to the essential profile and valuation metrics (saves ~90% tokens)
        compact_info = {
            "shortName": info.get("shortName") or info.get("longName"),
            "symbol": info.get("symbol", ticker),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "marketCap": info.get("marketCap"),
            "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice"),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "pegRatio": info.get("pegRatio"),
            "priceToBook": info.get("priceToBook"),
            "dividendYield": info.get("dividendYield"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "currency": info.get("currency"),
            "summary": (info.get("longBusinessSummary") or "")[:250] + (
                "..." if len(info.get("longBusinessSummary") or "") > 250 else ""
            ),
        }
        filtered_info = {k: v for k, v in compact_info.items() if v is not None}

        end_time = time.time()
        logger.info(f"Retrieved Company Info of {ticker} in {end_time - start_time:.3f} seconds")
        return filtered_info if filtered_info else info

    except TimeoutError:
        logger.warning(f"Company info lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Company info lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve company info of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve company info for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 8: Retrieve Dividend History
# --------------------------------------------------------------------------------
@tool("get_dividends", description="A function that returns the dividend payment history of a given ticker")
def get_dividends(ticker: str):
    logger.info(f"Retrieving Dividends of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "dividends")
        dividends = _safe_df_to_dict(
            raw_data,
            f"No dividends available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Dividends of {ticker} in {end_time - start_time:.3f} seconds")
        return dividends

    except TimeoutError:
        logger.warning(f"Dividends lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Dividends lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve dividends of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve dividends for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 9: Retrieve Stock Split History
# --------------------------------------------------------------------------------
@tool("get_splits", description="A function that returns the stock split history of a given ticker")
def get_splits(ticker: str):
    logger.info(f"Retrieving Stock Splits of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "splits")
        splits = _safe_df_to_dict(
            raw_data,
            f"No stock splits available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Stock Splits of {ticker} in {end_time - start_time:.3f} seconds")
        return splits

    except TimeoutError:
        logger.warning(f"Stock splits lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Stock splits lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve stock splits of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve stock splits for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 10: Retrieve Institutional Holders
# --------------------------------------------------------------------------------
@tool("get_institutional_holders", description="A function that returns the institutional ownership data of a given ticker")
def get_institutional_holders(ticker: str):
    logger.info(f"Retrieving Institutional Holders of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "institutional_holders")
        holders = _safe_df_to_dict(
            raw_data,
            f"No institutional holders available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Institutional Holders of {ticker} in {end_time - start_time:.3f} seconds")
        return holders

    except TimeoutError:
        logger.warning(f"Institutional holders lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Institutional holders lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve institutional holders of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve institutional holders for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 11: Retrieve Major Share Holders
# --------------------------------------------------------------------------------
@tool("get_major_shareholders", description="A function that returns the major share holder data of a given ticker")
def get_major_shareholders(ticker: str):
    logger.info(f"Retrieving Major Share Holders of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "major_holders")
        holders = _safe_df_to_dict(
            raw_data,
            f"No major share holders available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Major Share Holders of {ticker} in {end_time - start_time:.3f} seconds")
        return holders

    except TimeoutError:
        logger.warning(f"Major shareholders lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Major shareholders lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve major share holders of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve major share holders for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 12: Retrieve Mutual Fund Holders
# --------------------------------------------------------------------------------
@tool("get_mutual_fund_holders", description="A function that returns the mutual fund ownership data of a given ticker")
def get_mutual_fund_holders(ticker: str):
    logger.info(f"Retrieving Mutual Fund Holders of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "mutualfund_holders")
        holders = _safe_df_to_dict(
            raw_data,
            f"No mutual fund holders available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Mutual Fund Holders of {ticker} in {end_time - start_time:.3f} seconds")
        return holders

    except TimeoutError:
        logger.warning(f"Mutual fund holders lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Mutual fund holders lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve mutual fund holders of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve mutual fund holders for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 13: Retrieve Insider Transactions
# --------------------------------------------------------------------------------
@tool("get_insider_transactions", description="A function that returns the insider buy/sell transactions of a given ticker")
def get_insider_transactions(ticker: str):
    logger.info(f"Retrieving Insider Transactions of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "insider_transactions")
        insider_txn = _safe_df_to_dict(
            raw_data,
            f"No insider transactions available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Insider Transactions of {ticker} in {end_time - start_time:.3f} seconds")
        return insider_txn

    except TimeoutError:
        logger.warning(f"Insider transactions lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Insider transactions lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve insider transactions of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve insider transactions for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 14: Retrieve Analyst Recommendations
# --------------------------------------------------------------------------------
@tool("get_analyst_recommendations", description="A function that returns the analyst recommendations of a given ticker")
def get_analyst_recommendations(ticker: str):
    logger.info(f"Retrieving Analyst Recommendations of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "recommendations")
        recommendations = _safe_df_to_dict(
            raw_data,
            f"No analyst recommendations available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Analyst Recommendations of {ticker} in {end_time - start_time:.3f} seconds")
        return recommendations

    except TimeoutError:
        logger.warning(f"Analyst recommendations lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Analyst recommendations lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve analyst recommendations of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve analyst recommendations for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 15: Retrieve Analyst Recommendations Summary
# --------------------------------------------------------------------------------
@tool("get_analyst_recommendations_summary", description="A function that returns the analyst recommendations summary of a given ticker")
def get_analyst_recommendations_summary(ticker: str):
    logger.info(f"Retrieving Analyst Recommendations Summary of {ticker}")

    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Error: Invalid ticker provided. Please provide a valid ticker symbol."

    ticker = ticker.strip().upper()
    start_time = time.time()
    try:
        raw_data = _fetch_ticker_attr(ticker, "recommendations_summary")
        recommendations = _safe_df_to_dict(
            raw_data,
            f"No analyst recommendations summary available for {ticker}"
        )

        end_time = time.time()
        logger.info(f"Retrieved Analyst Recommendations Summary of {ticker} in {end_time - start_time:.3f} seconds")
        return recommendations

    except TimeoutError:
        logger.warning(f"Analyst recommendations summary lookup for {ticker} timed out after {DEFAULT_TOOL_TIMEOUT}s")
        return f"Error: Analyst recommendations summary lookup for {ticker} timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve analyst recommendations summary of {ticker}: {str(e)}")
        return f"Error: Failed to retrieve analyst recommendations summary for {ticker}. Please try again later."


# --------------------------------------------------------------------------------
# Tool 16: Retrieve Company's Ticker/Symbol
# --------------------------------------------------------------------------------
@tool("get_ticker", description="A function that returns the ticker/symbol of a given company")
def get_ticker(company_name: str):
    logger.info(f"Retrieving Ticker of {company_name}")

    if not company_name or not isinstance(company_name, str) or not company_name.strip():
        return "Error: Invalid company name provided. Please provide a valid company name."

    clean_name = company_name.strip()
    try:
        start_time = time.time()
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {
            "q": clean_name,
            "quotesCount": 5,
            "newsCount": 0,
            "enableFuzzyQuery": "false",
        }
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            params=params,
            timeout=DEFAULT_TOOL_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            quotes = data.get("quotes", [])
            if not quotes:
                return f"No ticker found for company: {clean_name}"

            ticker = quotes[0].get("symbol")
            if not ticker:
                return f"No ticker symbol found in results for company: {clean_name}"

            end_time = time.time()
            logger.info(f"Retrieved Ticker of {clean_name} ({ticker}) in {end_time - start_time:.3f} seconds")
            return ticker
        else:
            return f"Error: Failed to retrieve ticker (HTTP {response.status_code}). Please try again later."

    except requests.Timeout:
        logger.error(f"Timeout while retrieving ticker for {clean_name}")
        return "Error: Ticker lookup timed out. Please try again later."
    except Exception as e:
        logger.error(f"Failed to retrieve ticker of {clean_name}: {str(e)}")
        return f"Error: Failed to retrieve ticker for {clean_name}. Please try again later."
