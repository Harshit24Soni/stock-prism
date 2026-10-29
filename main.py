import os
import contextlib
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import SystemMessage, HumanMessage, AIMessageChunk
from langgraph.errors import GraphRecursionError
from openai import RateLimitError
from config.config import RequestObject
from StockPrism.components.agent import agent, is_agent_configured, get_effective_llm_config
from StockPrism.utils.logger import get_logger

logger = get_logger(__name__)
app = FastAPI(title="Stock Prism API", version="1.0.0")

# --------------------------------------------------------------------------------
# CORS Configuration
# --------------------------------------------------------------------------------
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
env_origins = os.getenv("CORS_ORIGINS", "")
if env_origins.strip():
    allowed_origins = [orig.strip() for orig in env_origins.split(",") if orig.strip()]
else:
    allowed_origins = default_origins

# If wildcard is requested, credentials must be disabled per CORS specification
allow_credentials = "*" not in allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------------
# Langfuse Observability Initialization
# --------------------------------------------------------------------------------
langfuse_client = None
langfuse_pk = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
langfuse_sk = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()

if langfuse_pk and langfuse_sk:
    try:
        from langfuse import Langfuse

        langfuse_client = Langfuse(
            public_key=langfuse_pk,
            secret_key=langfuse_sk,
            host=langfuse_host,
        )
        logger.info("Langfuse tracing enabled.")
    except Exception as exc:
        logger.warning(f"Failed to initialize Langfuse: {exc}. Tracing disabled.")
else:
    logger.info("Langfuse credentials not supplied. Tracing disabled.")


SYSTEM_PROMPT = (
    "You are a professional stock market analyst. For every user query, determine "
    "which specific tool can provide the needed data. Be targeted and efficient: call only the "
    "1-2 tools directly required to answer the specific question (e.g. price, profile, or news), "
    "rather than chaining multiple redundant tools. If the user does not provide an exact stock ticker, "
    "use get_ticker to resolve it first. Always use the resolved ticker symbol for subsequent tool calls. "
    "If any tool returns an error, times out, or indicates no data is available, do NOT retry the same "
    "tool with variations or fabricate data; simply explain what was found and what was unavailable. "
    "Provide clear, concise, and structured answers."
)


# --------------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Health check endpoint for service monitoring, orchestrators, and keep-alive pings."""
    llm_info = get_effective_llm_config()
    return {
        "status": "ok",
        "service": "Stock Prism Backend",
        "agent_configured": is_agent_configured(),
        "llm_provider": llm_info["provider"],
        "llm_model": llm_info["model"],
        "langfuse_enabled": langfuse_client is not None,
    }


@app.post("/api/chat")
async def chat(request: RequestObject):
    thread_id = request.threadId or "default_thread"
    recursion_limit = int(os.getenv("AGENT_RECURSION_LIMIT", "20"))
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": recursion_limit,
    }

    async def generate():
        # Check if agent is configured with a valid API key
        if not is_agent_configured():
            yield (
                "<custommarkdown>\n\n⚠️ **AI Model Not Configured**\n\n"
                "Please configure a free API key in your `.env` file to enable analysis:\n"
                "- **Groq (100% Free, Recommended):** Set `GROQ_API_KEY=gsk_...` in `.env` (Get from https://console.groq.com/)\n"
                "- **Google AI Studio (100% Free):** Set `GEMINI_API_KEY=AIzaSy...` in `.env` (Get from https://aistudio.google.com/)\n"
                "- **OpenAI / Custom:** Set `OPENAI_API_KEY=...` in `.env`\n\n</custommarkdown>"
            )
            return

        span = None
        generation = None
        custom_markdown_opened = False

        try:
            # Start Langfuse span if available
            if langfuse_client:
                span = langfuse_client.start_observation(
                    as_type="span",
                    name="chat-request",
                    input=request.prompt.content,
                    metadata={"user_id": thread_id},
                )
                generation = langfuse_client.start_observation(
                    as_type="generation",
                    name="agent-stream",
                    model=os.getenv("LLM_MODEL", "agentic-workflow"),
                    input=request.prompt.content,
                )

            # Emit opening custommarkdown tag for GenUI XML parser
            yield "<custommarkdown>"
            custom_markdown_opened = True
            full_response = ""
            async for token, _ in agent.astream(
                {
                    "messages": [
                        SystemMessage(content=SYSTEM_PROMPT),
                        HumanMessage(content=request.prompt.content),
                    ]
                },
                stream_mode="messages",
                config=config,
            ):
                # Filter to stream only assistant AI message chunks to the user
                # (Prevents raw internal ToolMessage outputs from dumping into chat)
                if not isinstance(token, AIMessageChunk) and getattr(token, "type", "") not in ("ai", "AIMessageChunk"):
                    continue

                content = token.content
                if isinstance(content, str) and content:
                    full_response += content
                    yield content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, str):
                            full_response += part
                            yield part
                        elif isinstance(part, dict) and "text" in part:
                            text_piece = part["text"]
                            full_response += text_piece
                            yield text_piece

            # Fallback if model executed tools but yielded no assistant text
            if not full_response:
                yield "The requested data has been processed, but no additional commentary was generated. Please ask a specific question if you need more details."

            # Emit closing custommarkdown tag
            yield "</custommarkdown>"
            custom_markdown_opened = False

            logger.info(f"Analysis completed and stream finalized ({len(full_response)} characters delivered).")

            # Finalize Langfuse observations
            if generation:
                generation.end(output=full_response)
            if span:
                span.end(output="Request completed successfully")

        except GraphRecursionError as e:
            logger.warning(f"Agent reached recursion limit ({recursion_limit}): {e}")
            if generation:
                generation.end(status_message=str(e), level="WARNING")
            if span:
                span.end(status_message=str(e), level="WARNING")
            if not custom_markdown_opened:
                yield "<custommarkdown>"
            yield (
                "\n\n⚠️ **Analysis Limit Reached:** "
                "The analysis completed its maximum allowable retrieval steps to protect responsiveness. "
                "Please query a more specific metric or topic."
            )
            yield "</custommarkdown>"

        except RateLimitError as e:
            headers = getattr(getattr(e, "response", None), "headers", {}) or {}
            retry_after = headers.get("retry-after") or headers.get("Retry-After")
            req_id = headers.get("x-request-id") or headers.get("request-id")

            # Extract provider error body/message safely
            err_msg = getattr(e, "message", None) or str(e) or ""
            err_lower = err_msg.lower()

            # Determine whether the specific limit is confirmed from error body or headers
            rem_tokens = headers.get("x-ratelimit-remaining-tokens")
            rem_requests = headers.get("x-ratelimit-remaining-requests")

            if "token" in err_lower or "tpm" in err_lower or rem_tokens == "0":
                limit_desc = "token quota (TPM)"
            elif "requests per day" in err_lower or "rpd" in err_lower or rem_requests == "0":
                limit_desc = "daily request quota (RPD)"
            elif "requests per minute" in err_lower or "rpm" in err_lower:
                limit_desc = "requests-per-minute quota (RPM)"
            else:
                # Neutral rate-limit message when specific cause is not confirmed
                limit_desc = "rate limit"

            # Sanitized log: include request ID and confirmed details without credentials
            log_detail = f" [{limit_desc}]" if limit_desc != "rate limit" else ""
            retry_log = f" | Retry-After: {retry_after}s" if retry_after else ""
            req_log = f" | Request ID: {req_id}" if req_id else ""
            logger.warning(
                f"Groq Rate Limit (429){log_detail}{req_log}{retry_log} | Detail: {err_msg}"
            )

            if generation:
                generation.end(status_message=err_msg, level="ERROR")
            if span:
                span.end(status_message=err_msg, level="ERROR")

            wait_str = (
                f" Please wait {retry_after} seconds before trying again."
                if retry_after
                else " Please wait a few moments before trying again."
            )
            req_str = f"\n(Request ID: `{req_id}`)" if req_id and req_id != "N/A" else ""

            if not custom_markdown_opened:
                yield "<custommarkdown>"

            if limit_desc != "rate limit":
                yield f"\n\n⚠️ **Rate Limit Exceeded (429):** Provider {limit_desc} reached.{wait_str}{req_str}"
            else:
                yield f"\n\n⚠️ **Rate Limit Exceeded (429):** Provider rate limit reached.{wait_str}{req_str}"
            yield "</custommarkdown>"

        except Exception as e:
            logger.error(f"Error during chat generation: {e}")
            if generation:
                generation.end(status_message=str(e), level="ERROR")
            if span:
                span.end(status_message=str(e), level="ERROR")

            if not custom_markdown_opened:
                yield "<custommarkdown>"

            err_str = str(e)
            if "404" in err_str:
                yield (
                    f"\n\n⚠️ **Model Error (404):** The model is unavailable or does not exist.\n"
                    f"Please check your `GROQ_MODEL` setting in `.env` (Default: `openai/gpt-oss-120b`).\n"
                    f"Details: {err_str}"
                )
            elif "401" in err_str:
                yield "\n\n⚠️ **Authentication Error (401):** Your API key was rejected. Please verify the key in your `.env` file."
            elif "429" in err_str:
                yield "\n\n⚠️ **Rate Limit Exceeded (429):** Provider rate limit reached. Please wait a few moments before trying again."
            else:
                yield f"\n\n[Error encountered while generating analysis: {err_str}]"
            yield "</custommarkdown>"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"App Initiating on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
