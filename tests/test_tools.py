import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from StockPrism.utils.tools import (
    _run_with_timeout,
    get_stock_price,
    get_historical_data,
    get_stock_news,
    get_balance_sheet,
    get_income_statement,
    get_cash_flow,
    get_company_info,
    get_dividends,
    get_splits,
    get_institutional_holders,
    get_major_shareholders,
    get_mutual_fund_holders,
    get_insider_transactions,
    get_analyst_recommendations,
    get_analyst_recommendations_summary,
    get_ticker,
)


class TestStockTools(unittest.TestCase):
    # ---------------------------------------------------------
    # Tool 1: get_stock_price
    # ---------------------------------------------------------
    def test_get_stock_price_invalid_ticker(self):
        result = get_stock_price.invoke({"ticker": ""})
        self.assertIn("Invalid ticker", result)
        result2 = get_stock_price.func(None)
        self.assertIn("Invalid ticker", result2)
        result3 = get_stock_price.invoke({"ticker": "   "})
        self.assertIn("Invalid ticker", result3)

    @patch("yfinance.Ticker")
    def test_get_stock_price_fast_info_success(self, mock_ticker):
        mock_instance = MagicMock()
        mock_fast_info = MagicMock()
        mock_fast_info.last_price = 185.50
        mock_instance.fast_info = mock_fast_info
        mock_ticker.return_value = mock_instance

        price = get_stock_price.invoke("AAPL")
        self.assertEqual(price, 185.50)

    @patch("yfinance.Ticker")
    def test_get_stock_price_fallback_info(self, mock_ticker):
        mock_instance = MagicMock()
        mock_instance.fast_info = None
        mock_instance.info = {"currentPrice": 220.00}
        mock_ticker.return_value = mock_instance

        price = get_stock_price.invoke("MSFT")
        self.assertEqual(price, 220.00)

    @patch("yfinance.Ticker")
    def test_get_stock_price_no_price_available(self, mock_ticker):
        mock_instance = MagicMock()
        mock_instance.fast_info = None
        mock_instance.info = {}
        mock_ticker.return_value = mock_instance

        result = get_stock_price.invoke("XYZ")
        self.assertEqual(result, "No price data available for XYZ")
        # Ensure it does NOT contain the literal "{ticker}"
        self.assertNotIn("{ticker}", result)

    # ---------------------------------------------------------
    # Tool 2: get_historical_data
    # ---------------------------------------------------------
    def test_get_historical_data_invalid_input(self):
        result = get_historical_data.invoke({"ticker": "", "start_date": "2024-01-01", "end_date": "2024-01-10"})
        self.assertIn("Invalid ticker", result)

    @patch("yfinance.Ticker")
    def test_get_historical_data_success(self, mock_ticker):
        mock_instance = MagicMock()
        mock_df = pd.DataFrame(
            {"Close": [150.0, 155.0]},
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )
        mock_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_instance

        result = get_historical_data.invoke({"ticker": "AAPL", "start_date": "2024-01-01", "end_date": "2024-01-10"})
        self.assertIsInstance(result, dict)
        self.assertIn("Close", result)

    @patch("yfinance.Ticker")
    def test_get_historical_data_empty(self, mock_ticker):
        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_instance

        result = get_historical_data.invoke({"ticker": "AAPL", "start_date": "2024-01-01", "end_date": "2024-01-10"})
        self.assertIn("No historical data available", result)
        self.assertNotIn("{ticker}", result)

    # ---------------------------------------------------------
    # Tool 3: get_stock_news
    # ---------------------------------------------------------
    @patch("yfinance.Ticker")
    def test_get_stock_news_success(self, mock_ticker):
        mock_instance = MagicMock()
        mock_instance.news = [{"title": "Market hits all-time high"}]
        mock_ticker.return_value = mock_instance

        news = get_stock_news.invoke("AAPL")
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]["title"], "Market hits all-time high")

    @patch("yfinance.Ticker")
    def test_get_stock_news_empty(self, mock_ticker):
        mock_instance = MagicMock()
        mock_instance.news = []
        mock_ticker.return_value = mock_instance

        result = get_stock_news.invoke("UNKNOWN")
        self.assertEqual(result, "No news available for UNKNOWN")
        self.assertNotIn("{ticker}", result)

    @patch("StockPrism.utils.tools._run_with_timeout", side_effect=TimeoutError("Operation timed out"))
    def test_get_stock_news_timeout(self, mock_run):
        result = get_stock_news.invoke("JPL.NS")
        self.assertIn("lookup timed out", result)
        self.assertIn("JPL.NS", result)

    @patch("yfinance.Ticker")
    def test_get_stock_news_malformed(self, mock_ticker):
        mock_instance = MagicMock()
        # Mix of None, non-dict, and dict without title
        mock_instance.news = [None, "invalid_str", {}, {"title": "Valid News", "publisher": "Reuters"}]
        mock_ticker.return_value = mock_instance

        result = get_stock_news.invoke("AAPL")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Valid News")
        self.assertEqual(result[0]["publisher"], "Reuters")

    # ---------------------------------------------------------
    # Tools 4, 5, 6: Financial Statements
    # ---------------------------------------------------------
    @patch("yfinance.Ticker")
    def test_financial_statements_with_none_and_empty(self, mock_ticker):
        mock_instance = MagicMock()
        mock_instance.balance_sheet = None
        mock_instance.financials = pd.DataFrame()
        mock_instance.cashflow = None
        mock_ticker.return_value = mock_instance

        bs = get_balance_sheet.invoke("AAPL")
        self.assertEqual(bs, "No balance sheet available for AAPL")
        self.assertNotIn("{ticker}", bs)

        inc = get_income_statement.invoke("AAPL")
        self.assertEqual(inc, "No income statement available for AAPL")
        self.assertNotIn("{ticker}", inc)

        cf = get_cash_flow.invoke("AAPL")
        self.assertEqual(cf, "No cash flow available for AAPL")
        self.assertNotIn("{ticker}", cf)

    # ---------------------------------------------------------
    # Tool 7: get_company_info
    # ---------------------------------------------------------
    @patch("yfinance.Ticker")
    def test_get_company_info(self, mock_ticker):
        mock_instance = MagicMock()
        mock_instance.info = {"shortName": "Apple Inc.", "sector": "Technology"}
        mock_ticker.return_value = mock_instance

        info = get_company_info.invoke("AAPL")
        self.assertEqual(info["shortName"], "Apple Inc.")

    # ---------------------------------------------------------
    # Tools 8-15: Ownership, Dividends, Splits & Analyst Tools
    # ---------------------------------------------------------
    @patch("yfinance.Ticker")
    def test_corporate_actions_and_ownership(self, mock_ticker):
        mock_instance = MagicMock()
        mock_instance.dividends = pd.Series([0.25], index=pd.to_datetime(["2024-02-09"]))
        mock_instance.splits = pd.Series(dtype=float)
        mock_instance.institutional_holders = None
        mock_instance.major_holders = None
        mock_instance.mutualfund_holders = None
        mock_instance.insider_transactions = None
        mock_instance.recommendations = None
        mock_instance.recommendations_summary = None
        mock_ticker.return_value = mock_instance

        div = get_dividends.invoke("AAPL")
        self.assertIsInstance(div, dict)

        splits = get_splits.invoke("AAPL")
        self.assertEqual(splits, "No stock splits available for AAPL")
        self.assertNotIn("{ticker}", splits)

        inst = get_institutional_holders.invoke("AAPL")
        self.assertEqual(inst, "No institutional holders available for AAPL")

        rec = get_analyst_recommendations.invoke("AAPL")
        self.assertEqual(rec, "No analyst recommendations available for AAPL")

    # ---------------------------------------------------------
    # Tool 16: get_ticker
    # ---------------------------------------------------------
    def test_get_ticker_invalid_input(self):
        result = get_ticker.invoke("")
        self.assertIn("Invalid company name", result)

    @patch("requests.get")
    def test_get_ticker_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"quotes": [{"symbol": "NVDA"}]}
        mock_get.return_value = mock_resp

        ticker = get_ticker.invoke("NVIDIA")
        self.assertEqual(ticker, "NVDA")
        # Verify custom user agent was sent
        headers_sent = mock_get.call_args[1].get("headers", {})
        self.assertIn("User-Agent", headers_sent)

    @patch("requests.get")
    def test_get_ticker_no_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"quotes": []}
        mock_get.return_value = mock_resp

        result = get_ticker.invoke("NonExistentCo123")
        self.assertIn("No ticker found", result)
        self.assertNotIn("{company_name}", result)

    @patch("requests.get")
    def test_get_ticker_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp

        result = get_ticker.invoke("Apple")
        self.assertIn("HTTP 403", result)

    def test_run_with_timeout_success(self):
        def sample_func(x):
            return x * 2

        res = _run_with_timeout(sample_func, 21, timeout=2.0)
        self.assertEqual(res, 42)

    def test_run_with_timeout_triggers_timeout_error(self):
        import time

        def slow_func():
            time.sleep(1.0)
            return "done"

        with self.assertRaises(TimeoutError):
            _run_with_timeout(slow_func, timeout=0.1)


if __name__ == "__main__":
    unittest.main()
