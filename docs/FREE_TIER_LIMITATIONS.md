# Stock Prism: Free-Tier Limitations & Cost-Safety Report

**Objective:** Guarantee **zero unexpected charges**, transparent resource boundaries, and predictable operational behavior when running Stock Prism completely free of charge.

---

## 1. Provider-by-Provider Free Tier Breakdown

### A. Groq Cloud (Recommended AI Model Provider)
- **Official Plan:** Developer Free Tier
- **Cost:** \$0.00 / month
- **Credit Card / Payment Method Required:** **NO** (Sign in with GitHub/Google).
- **Surprise Charge Risk:** **Zero**. Groq does not have your billing information. When limits are exceeded, requests return HTTP 429 rather than billing you.
- **Quotas & Limits (for `openai/gpt-oss-120b`):**
  - **Requests Per Minute (RPM):** 30 requests / min (maximum allowed in a rolling 60-second window).
  - **Requests Per Day (RPD):** 1,000 requests / day (cumulative 24-hour limit; reported by Groq in the `x-ratelimit-limit-requests` header. **Note:** Do not confuse this daily limit with RPM).
  - **Tokens Per Minute (TPM):** 8,000 tokens / min (total input + output tokens processed in a rolling 60-second window; reported in the `x-ratelimit-limit-tokens` header).
- **Inactivity Behavior:** Keys do not expire due to inactivity.
- **What happens when quota is exhausted?**
  - If you exceed RPM, RPD, or TPM limits, Groq temporarily pauses requests with an HTTP 429 (Rate Limit Exceeded) error.
  - The Stock Prism backend inspects the error message and response headers to determine whether the trigger was a token limit, request limit, or general throttle, and displays a clean, neutral message along with the exact seconds to wait (from `Retry-After`).
- **Best Practices to Stay Within Limits:**
  - Avoid rapid double-clicking or benchmark loops. Normal conversational queries consume ~2,000–2,500 cumulative tokens across multi-turn tool loops, allowing ~3 full analyses per minute before the 8,000 TPM limit resets.

---

### B. Google AI Studio (Alternative AI Model Provider)
- **Official Plan:** Gemini API Free Tier
- **Cost:** \$0.00 / month
- **Credit Card / Payment Method Required:** **NO** when created directly at `https://aistudio.google.com/`.
- **Surprise Charge Risk:** **Zero** on AI Studio unlinked projects.
- **Quotas & Limits (for `gemini-2.0-flash`):**
  - **Requests Per Minute (RPM):** 15 requests / min.
  - **Requests Per Day (RPD):** 1,500 requests / day.
  - **Tokens Per Minute (TPM):** 1,000,000 tokens / min.
- **Data Policy Note:** On Google AI Studio's free tier, prompts may be sampled by Google to improve model quality (standard for free LLMs). Never transmit confidential personal data or trade secrets.
- **What happens when quota is exhausted?**
  - The API returns HTTP 429 until the daily or per-minute window resets.

---

### C. Yahoo Finance (`yfinance` & Search API)
- **Official Plan:** Public Web Interface / Open Source Scraper
- **Cost:** \$0.00 / month (No account, no key needed).
- **Credit Card / Payment Method Required:** **NO**.
- **Quotas & Restrictions:**
  - Yahoo Finance does not publish an official SLA for open requests.
  - Standard rate limit is approximately 2,000 requests per IP address per hour.
- **Inactivity Behavior:** Always available.
- **Surprise Charge Risk:** **Zero** (no account or billing mechanism exists).
- **Reliability Note:** Yahoo Finance occasionally changes internal page schemas. `yfinance` is actively maintained by the open-source community to adapt to changes.

---

### D. Render (Backend Web Service Hosting)
- **Official Plan:** Individual Free Tier
- **Cost:** \$0.00 / month
- **Credit Card Required:** **NO** for free web services and static sites.
- **Included Resources:**
  - 750 free instance hours per calendar month (enough to run 1 free service continuously 24/7 all month).
  - 512 MB RAM / 0.1 vCPU.
- **Critical Operational Limitation - Inactivity Spin-Down:**
  - On the free plan, Render automatically spins down your web service if it receives no web traffic for **15 consecutive minutes**.
  - When the next request arrives (e.g. when you open the frontend after a break), Render spins up the container.
  - **Cold Start Time:** The first request takes **30 to 50 seconds** to boot. Once booted, all subsequent requests respond in sub-second speeds.
  - This is standard behavior across free cloud tiers and costs \$0.00.
- **Surprise Charge Risk:** **Zero**. Render does not automatically convert free instances to paid tiers without explicit manual upgrades.

---

### E. Vercel (Frontend Edge Hosting)
- **Official Plan:** Hobby Free Tier
- **Cost:** \$0.00 / month
- **Credit Card Required:** **NO**.
- **Included Resources:**
  - 100 GB global bandwidth per month.
  - Unlimited static asset deployments.
  - Free automatic SSL certificates (`.vercel.app`).
  - No spin-down / no cold starts (static frontend is distributed across Vercel’s global CDN edge).
- **Surprise Charge Risk:** **Zero**. Vercel Hobby accounts have hard caps that pause deployments rather than auto-charging credit cards.

---

## 2. Cost-Safety Summary Checklist

| Service | Plan | Monthly Cost | Can It Bill My Card? | Cold Start / Inactivity | Action if Exceeded |
|---|---|---|---|---|---|
| **Groq Cloud** | Developer Free | **\$0.00** | **NO** | None | Temporary 60s pause (HTTP 429) |
| **Google AI Studio** | Free Tier | **\$0.00** | **NO** | None | Pauses until daily reset |
| **Yahoo Finance** | Public / Open | **\$0.00** | **NO** | None | Temporary HTTP 429 if throttled |
| **Render** | Free Web Service | **\$0.00** | **NO** | Spins down after 15m idle (30s boot) | Monthly free hour cap |
| **Vercel** | Hobby | **\$0.00** | **NO** | Zero cold start | Pauses until monthly reset |

**Final Guarantee:** By following the architecture in [`docs/DEPLOYMENT_GUIDE.md`](file:///E:/College/7th%20Semester/Minor%20Project/Stock%20Prism/docs/DEPLOYMENT_GUIDE.md), you will operate Stock Prism with **total financial safety, \$0.00 cost, and zero hidden billing triggers**.

