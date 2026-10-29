# Stock Prism: API & Service Requirements Inventory

**Document Purpose:** Complete, verified inventory of all external services, APIs, and data sources required to run and deploy Stock Prism without incurring costs.

---

## 1. Complete Service Inventory Table

| Service / Provider | Purpose in Stock Prism | Code Location | Required? | Current Status | API Key Required? | Free Availability | Billing / Card Required? | Rate Limits & Quotas | Genuinely Free Alternative | Setup Instructions Link |
|---|---|---|---|---|---|---|---|---|---|---|
| **Groq Cloud API** | Primary LLM inference (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`) & agent tool execution | [`StockPrism/components/agent.py`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/StockPrism/components/agent.py) | **Yes** (1 AI provider needed) | Verified & Tested Live | **Yes** (`GROQ_API_KEY`) | **Verified Permanent Free Tier** | **No** (Email/GitHub signup only) | 30 requests/min, 14,400 requests/day, 6,000 tokens/min | Google AI Studio (Gemini) | [console.groq.com](https://console.groq.com/) |
| **Google AI Studio (Gemini)** | Alternative LLM inference (Gemini 2.0 Flash) | [`StockPrism/components/agent.py`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/StockPrism/components/agent.py) | Optional alternative | Verified & Supported | **Yes** (`GEMINI_API_KEY`) | **Verified Permanent Free Tier** | **No** (Standard Google account) | 15 requests/min, 1,500 requests/day, 1M tokens/min | Groq Cloud | [aistudio.google.com](https://aistudio.google.com/) |
| **OpenAI API** | Legacy LLM provider (`gpt-4o-mini`, etc.) | [`StockPrism/components/agent.py`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/StockPrism/components/agent.py) | Optional | Supported | **Yes** (`OPENAI_API_KEY`) | **Not Suitable for Free Use** | **Yes** (Requires \$5 minimum prepaid credit card billing) | Per tier | Use Groq or Google AI Studio | [platform.openai.com](https://platform.openai.com/) |
| **TheSys C1 (GenUI)** | Generative UI streaming model | [`StockPrism/components/agent.py`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/StockPrism/components/agent.py) | Optional | Fallback | **Yes** | Limited invite beta | Waitlist / Private | Varies | Use Groq or Google AI Studio | [thesys.dev](https://thesys.dev/) |
| **Yahoo Finance (`yfinance`)** | Stock quotes, history, financial statements, balance sheets, news, corporate holders | [`StockPrism/utils/tools.py`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/StockPrism/utils/tools.py#L40-L480) | **Yes** (Core market data) | Verified Working | **NO** (Zero keys needed) | **100% Free Public Access** | **No** | ~2,000 requests/hour IP rate limit | Alpha Vantage / Finnhub (Free tiers) | Python package `yfinance` |
| **Yahoo Finance Search API** | Resolving company names to stock ticker symbols | [`StockPrism/utils/tools.py`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/StockPrism/utils/tools.py#L487-L527) | **Yes** (`get_ticker`) | Verified Working | **NO** (Zero keys needed) | **100% Free Public Access** | **No** | Standard HTTP throttling | SEC EDGAR company tickers lookup | Native HTTP query |
| **Langfuse** | LLM tracing, latency monitoring & span observability | [`main.py`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/main.py#L36-L55) | **Optional** (Gracefully skips if empty) | Supported | Optional (`LANGFUSE_PUBLIC_KEY`) | Generous Free Tier | **No** (Free cloud tier available) | 50,000 observations/month | Built-in Python logging ([`logger.py`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/StockPrism/utils/logger.py)) | [cloud.langfuse.com](https://cloud.langfuse.com/) |
| **Database (Supabase / PostgreSQL)** | Persistent storage, user accounts, message history | None in codebase | **NOT NEEDED** | N/A | **NO** | N/A | N/A | N/A | LangGraph in-memory `MemorySaver` | N/A (Do not configure) |
| **Render Web Service** | Backend hosting (FastAPI, Uvicorn, LangGraph) | [`render.yaml`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/render.yaml) | **Yes** (Production deployment) | Verified Compatible | **No** (Account login) | **Verified Free Tier** | **No** (No card required for free web service) | 750 free instance hours/month, spins down after 15 min idle | Railway / Koyeb | [render.com](https://render.com/) |
| **Vercel / Render Static Site** | Frontend hosting (React 19, TypeScript, Vite) | [`frontend/`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/frontend/) | **Yes** (Production deployment) | Verified Compatible | **No** (Account login) | **Verified Free Tier** | **No** | 100GB bandwidth/month, fast global edge CDN | Cloudflare Pages / Netlify | [vercel.com](https://vercel.com/) |

---

## 2. Minimum Required API Keys Checklist

To run Stock Prism with 100% functionality both locally and in production, you need:

### You MUST obtain exactly ONE free key:
- [ ] **`GROQ_API_KEY`** (Recommended) from [Groq Console](https://console.groq.com/keys)  
  *OR*
- [ ] **`GEMINI_API_KEY`** from [Google AI Studio](https://aistudio.google.com/app/apikey)

### You DO NOT need keys for:
- ❌ Market Data (Stock prices, historical charts, financial statements, dividends, analyst ratings) -> **Zero keys needed** (Powered by `yfinance`).
- ❌ Ticker Search (Searching "Apple" -> "AAPL") -> **Zero keys needed** (Powered by Yahoo Search).
- ❌ Database -> **Zero keys needed** (Stock Prism uses in-memory session threads via LangGraph `MemorySaver`).
- ❌ Langfuse -> **Zero keys needed** (Optional; backend runs smoothly with tracing disabled).
- ❌ Frontend UI components -> **Zero keys needed** (Client bundle is self-contained).

---

## 3. Why Supabase Is Not Needed

A thorough code audit of all 1,200+ lines in the repository confirms:
1. There are **zero database models**, zero ORMs (no SQLAlchemy, Prisma, Peewee, or Tortoise), and zero SQL migration scripts.
2. The agent stores conversation state in-memory per HTTP session using LangGraph's native `MemorySaver`:
   ```python
   agent = create_agent(model, tools=ALL_TOOLS, checkpointer=MemorySaver())
   ```
3. Stock market data is fetched on-demand in real-time from Yahoo Finance rather than stored in a persistent database.
4. **Recommendation:** Do not configure or link Supabase. Adding a database would introduce connection pooling latency, credentials management risks, and potential inactivity pausing without any functional benefit.

