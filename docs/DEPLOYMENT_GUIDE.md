# Stock Prism: Step-by-Step Deployment Guide (100% Free)

**Target Audience:** Students & Developers  
**Total Cost:** \$0.00 (Permanently Free Services, Zero Credit Card Required)  
**Hosting Architecture:**
- **Backend:** Render Free Web Service (FastAPI / Python 3.13)
- **Frontend:** Vercel Hobby Tier or Render Static Site (React 19 / Vite Edge CDN)
- **AI Engine:** Groq Cloud (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`) or Google AI Studio (`gemini-2.0-flash`)
- **Data Engine:** Yahoo Finance (`yfinance` - Zero API key requirement)

---

## Stage A: Local Verification Before Deployment

Before deploying to the cloud, verify that the application compiles and passes all checks on your machine:

1. **Run the backend test suite:**
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
   ```
   *Expected result: 30 tests pass with code 0.*

2. **Verify frontend linting & production compilation:**
   ```powershell
   cd frontend
   npm run lint
   npm run build
   cd ..
   ```
   *Expected result: `dist/` directory generated with zero errors.*

3. **Verify Git clean state & secrets safety:**
   Ensure `.env` is listed in `.gitignore` so your private API keys are never pushed to GitHub:
   ```powershell
   git status
   ```

---

## Stage B: Obtain Your Free AI Model API Key

Choose **ONE** of the following two providers (both require zero credit card):

### Option 1: Groq Cloud (Recommended - Fastest Inference)
1. Go to [https://console.groq.com/](https://console.groq.com/)
2. Click **Sign In** and sign in with your GitHub or Google account.
3. In the left navigation bar, click **API Keys**.
4. Click **Create API Key**, name it `stock-prism`, and click **Create**.
5. Copy your key (starts with `gsk_...`). Save it securely.

### Option 2: Google AI Studio (Alternative)
1. Go to [https://aistudio.google.com/](https://aistudio.google.com/)
2. Sign in with your standard Google account.
3. Click **Get API key** in the top left.
4. Click **Create API key in new project**.
5. Copy your key (starts with `AIzaSy...`).

---

## Stage C: Local Run & Verification

1. **Configure `.env` file:**
   Open `.env` in the project root and paste your key:
   ```env
   GROQ_API_KEY=gsk_your_key_here
   PORT=8000
   ```
   *(Or if using Gemini: `GEMINI_API_KEY=AIzaSy_your_key_here`)*

2. **Start the backend in Terminal 1:**
   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```
   *Expected log output:*
   ```
   [INFO]: Initializing AI agent with provider: Groq (Model: llama-3.3-70b-versatile)
   [INFO]: Agent Initiated Successfully
   [INFO]: App Initiating on port 8000
   INFO: Uvicorn running on http://0.0.0.0:8000
   ```

3. **Verify the backend health check:**
   In your browser or PowerShell:
   ```powershell
   curl http://localhost:8000/health
   ```
   *Response:*
   ```json
   {
     "status": "ok",
     "service": "Stock Prism Backend",
     "agent_configured": true,
     "llm_provider": "Groq",
     "llm_model": "llama-3.3-70b-versatile",
     "langfuse_enabled": false
   }
   ```

4. **Start the frontend in Terminal 2:**
   ```powershell
   cd frontend
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.
   Test a prompt: *"What is the stock price of Apple?"*
   *Result: The agent calls `get_stock_price('AAPL')` and streams the real-time quote directly into the chat interface!*

---

## Stage D: Push to GitHub

Initialize Git (if not already initialized) and push your code to your personal GitHub repository:

```powershell
git init
git add .
git commit -m "feat: production ready Stock Prism with zero-cost AI provider support"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/stock-prism.git
git push -u origin main
```

> [!IMPORTANT]
> Verify on GitHub that `.env` is **NOT** present in your online repository. Only `.env.example` should be committed.

---

## Stage E: Deploy Backend to Render (Free Web Service)

1. Sign up or log in at [https://render.com/](https://render.com/) using your GitHub account.
2. In the Render Dashboard, click **New +** -> **Web Service**.
3. Select **Build and deploy from a Git repository** and connect your `stock-prism` repository.
4. Fill in the service configuration:
   - **Name:** `stock-prism-backend`
   - **Region:** Choose the region closest to you (e.g., *Oregon (US West)*, *Frankfurt (EU)*, or *Singapore*).
   - **Branch:** `main`
   - **Root Directory:** Leave empty (defaults to repository root).
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free` (0.1 CPU, 512 MB RAM)
5. Scroll down to **Environment Variables** and add:
   - `PYTHON_VERSION` = `3.13.0`
   - `GROQ_API_KEY` = `gsk_your_groq_key_here` *(or `GEMINI_API_KEY`)*
   - `CORS_ORIGINS` = `*` *(or update with your frontend URL once deployed)*
6. Click **Advanced** and set:
   - **Health Check Path:** `/health`
7. Click **Create Web Service**.
8. Wait 2-3 minutes for the build to finish. Once live, Render will provide a public URL like:
   `https://stock-prism-backend.onrender.com`
9. Test your live backend by visiting:
   `https://stock-prism-backend.onrender.com/health` in your browser. It should return `{"status": "ok", "agent_configured": true}`.

---

## Stage F: Deploy Frontend to Vercel (Free Edge CDN)

1. Sign up or log in at [https://vercel.com/](https://vercel.com/) with GitHub.
2. Click **Add New...** -> **Project**.
3. Import your `stock-prism` GitHub repository.
4. Configure the project:
   - **Framework Preset:** `Vite`
   - **Root Directory:** Click **Edit** and select `frontend`.
   - **Build Command:** `npm run build` (or leave default).
   - **Output Directory:** `dist` (default).
5. Expand the **Environment Variables** section and add:
   - `VITE_API_URL` = `https://stock-prism-backend.onrender.com/api/chat`  
     *(Replace with your actual Render backend URL followed by `/api/chat`)*
6. Click **Deploy**.
7. In ~60 seconds, Vercel will assign a public URL like:
   `https://stock-prism.vercel.app`

---

## Stage G: Final End-to-End Verification

1. Open your live frontend URL (`https://stock-prism.vercel.app`).
2. Verify that the UI loads and the dark-mode theme displays properly.
3. Test a quick recommendation prompt or type:
   *"Compare the price and P/E ratio of Microsoft and Apple."*
4. Confirm:
   - Backend receives the request.
   - The agent calls `get_ticker` and `get_stock_price` / `get_company_info`.
   - The response streams smoothly to your screen.
5. **(Security Hardening):** Go back to Render Dashboard -> `stock-prism-backend` -> **Environment**, update:
   `CORS_ORIGINS` = `https://stock-prism.vercel.app`
   This restricts your backend API so only your frontend can call it!

