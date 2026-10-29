import os
import time
import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from StockPrism.utils.tools import (
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
from StockPrism.utils.logger import get_logger
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent

load_dotenv()
logger = get_logger(__name__)

# Default Groq model with verified availability, tool calling, and streaming support
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

ALL_TOOLS = [
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
]


def get_effective_llm_config():
    """
    Resolves the LLM configuration with zero-friction free tier support:
    - Auto-detects Groq (Free, no credit card) via GROQ_API_KEY or 'gsk_' prefix.
      Configurable via GROQ_MODEL or LLM_MODEL (defaults to 'openai/gpt-oss-120b').
    - Auto-detects Google AI Studio Gemini (Free, no credit card) via GEMINI_API_KEY or 'AIzaSy' prefix.
    - Supports custom OpenAI / TheSys C1 configurations via OPENAI_API_KEY.
    """
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    custom_base_url = os.getenv("LLM_BASE_URL", "").strip()
    preferred_provider = os.getenv("LLM_PROVIDER", "").strip().lower()

    # Priority for Groq model selection: GROQ_MODEL -> LLM_MODEL -> DEFAULT_GROQ_MODEL
    groq_model = os.getenv("GROQ_MODEL", "").strip() or os.getenv("LLM_MODEL", "").strip() or DEFAULT_GROQ_MODEL
    custom_model = os.getenv("LLM_MODEL", "").strip()

    # Explicit preference: Gemini
    if preferred_provider in ("gemini", "google", "google_ai_studio"):
        effective_key = gemini_key or openai_key
        if effective_key and effective_key not in ("your_api_key_here", "placeholder_key"):
            return {
                "api_key": effective_key,
                "base_url": custom_base_url or "https://generativelanguage.googleapis.com/v1beta/openai/",
                "model": custom_model or "gemini-2.0-flash",
                "provider": "Google AI Studio",
            }

    # Explicit preference: Groq
    if preferred_provider in ("groq",):
        effective_key = groq_key or openai_key
        if effective_key and effective_key not in ("your_api_key_here", "placeholder_key"):
            return {
                "api_key": effective_key,
                "base_url": custom_base_url or "https://api.groq.com/openai/v1",
                "model": groq_model,
                "provider": "Groq",
            }

    # 1. Groq explicit key (Default Free Provider)
    if groq_key and groq_key not in ("your_api_key_here", "placeholder_key"):
        return {
            "api_key": groq_key,
            "base_url": custom_base_url or "https://api.groq.com/openai/v1",
            "model": groq_model,
            "provider": "Groq",
        }

    # 2. Google AI Studio explicit key (Alternative Free Provider)
    if gemini_key and gemini_key not in ("your_api_key_here", "placeholder_key"):
        return {
            "api_key": gemini_key,
            "base_url": custom_base_url or "https://generativelanguage.googleapis.com/v1beta/openai/",
            "model": custom_model or "gemini-2.0-flash",
            "provider": "Google AI Studio",
        }

    # 3. OPENAI_API_KEY with auto-detection for Groq or Gemini keys
    if openai_key and openai_key not in ("your_api_key_here", "placeholder_key"):
        # Auto-detect Groq key pasted into OPENAI_API_KEY
        if openai_key.startswith("gsk_") and not custom_base_url:
            return {
                "api_key": openai_key,
                "base_url": "https://api.groq.com/openai/v1",
                "model": groq_model,
                "provider": "Groq (Auto-detected)",
            }
        # Auto-detect Google AI Studio key pasted into OPENAI_API_KEY
        if openai_key.startswith("AIzaSy") and not custom_base_url:
            return {
                "api_key": openai_key,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "model": custom_model or "gemini-2.0-flash",
                "provider": "Google AI Studio (Auto-detected)",
            }

        # Standard OpenAI or custom base URL (e.g. TheSys C1)
        return {
            "api_key": openai_key,
            "base_url": custom_base_url or "https://api.thesys.dev/v1/embed/",
            "model": custom_model or "c1/openai/gpt-5/v-20250930",
            "provider": "OpenAI / Custom",
        }

    # Unconfigured / Standby mode
    return {
        "api_key": "placeholder_key",
        "base_url": custom_base_url or "https://api.groq.com/openai/v1",
        "model": groq_model,
        "provider": "Unconfigured",
    }


def is_agent_configured() -> bool:
    """Check if a valid LLM API key has been provided."""
    config = get_effective_llm_config()
    return config["provider"] != "Unconfigured"


async def _log_llm_request(request: httpx.Request):
    """Store timestamp on request extension without logging any sensitive headers or keys."""
    request.extensions["start_time"] = time.time()


async def _log_llm_response(response: httpx.Response):
    """Safely log model request duration, status, request ID, and rate-limit headers."""
    start_time = response.request.extensions.get("start_time", time.time())
    duration = time.time() - start_time
    status = response.status_code
    headers = response.headers
    req_id = headers.get("x-request-id") or headers.get("request-id", "N/A")

    if status == 429:
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        rem_tokens = headers.get("x-ratelimit-remaining-tokens")
        limit_tokens = headers.get("x-ratelimit-limit-tokens")
        rem_requests = headers.get("x-ratelimit-remaining-requests")
        limit_requests = headers.get("x-ratelimit-limit-requests")

        details = []
        if retry_after:
            details.append(f"Retry-After: {retry_after}s")
        if rem_tokens is not None and limit_tokens is not None:
            details.append(f"Tokens: {rem_tokens}/{limit_tokens}")
        if rem_requests is not None and limit_requests is not None:
            details.append(f"Daily Requests: {rem_requests}/{limit_requests}")

        detail_str = f" | {', '.join(details)}" if details else ""
        logger.warning(
            f"LLM Rate Limit (429) hit | Request ID: {req_id} | Duration: {duration:.3f}s{detail_str}"
        )
    elif status >= 400:
        logger.error(
            f"LLM Request Failed ({status}) | Request ID: {req_id} | Duration: {duration:.3f}s"
        )
    else:
        logger.info(
            f"LLM Request Succeeded ({status}) | Request ID: {req_id} | Duration: {duration:.3f}s"
        )


def build_agent():
    """Build the LangGraph agent with fallback credentials if unconfigured."""
    config = get_effective_llm_config()
    if config["provider"] == "Unconfigured":
        logger.warning(
            "No LLM API key configured. Initializing agent in standby mode. "
            "Set GROQ_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY in your .env file."
        )
    else:
        logger.info(
            f"Initializing AI agent with provider: {config['provider']} "
            f"(Model: {config['model']})"
        )

    # Bounded retries with exponential backoff on retryable HTTP errors (429, 5xx)
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))

    http_client = httpx.AsyncClient(
        event_hooks={
            "request": [_log_llm_request],
            "response": [_log_llm_response],
        },
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "30.0")),
    )

    model = ChatOpenAI(
        model=config["model"],
        base_url=config["base_url"],
        api_key=config["api_key"],
        temperature=0.0,
        max_retries=max_retries,
        http_async_client=http_client,
    )

    created_agent = create_agent(
        model,
        tools=ALL_TOOLS,
        checkpointer=MemorySaver(),
    )
    return created_agent


agent = build_agent()
logger.info("Agent Initiated Successfully")
