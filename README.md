# Stock Prism

An AI-powered stock market analysis platform that provides comprehensive financial data and intelligent insights through a conversational interface.

## Overview

Stock Prism leverages advanced AI agents to deliver real-time stock market information, financial analysis, and investment insights. The platform combines the power of LangChain and OpenAI's language models with Yahoo Finance data to create an intelligent assistant for stock market research.

## Technology Stack

**Backend:**
- FastAPI for high-performance API endpoints
- LangChain & LangGraph for AI agent orchestration
- OpenAI / TheSys GPT models for intelligent responses
- YFinance for financial data retrieval
- Langfuse for observability and tracing

**Frontend:**
- Modern React 19 interface with TypeScript
- Real-time streaming responses
- Generative UI components via TheSys GenUI SDK
- Responsive design for all devices

## Getting Started

### Prerequisites
- Python 3.13+
- Node.js (v18+)
- LLM API key (OpenAI / TheSys)

### Installation

1. Clone the repository
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables in `.env` file (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```
4. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```
5. Run the backend server:
   ```bash
   python main.py
   ```
6. Run the frontend development server:
   ```bash
   cd frontend
   npm run dev
   ```
7. Access the API at `http://localhost:8000` and frontend at `http://localhost:5173`

### Testing

Run the automated test suite covering financial tools, agent orchestration, logging, and FastAPI endpoints:
```bash
python -m unittest discover -s tests -p "test_*.py"
```
Or via npm:
```bash
npm test
```

## Project Structure

```
Stock Prism/
├── StockPrism/         # Core AI package
│   ├── components/     # AI agent configuration (agent.py)
│   └── utils/          # Financial analysis tools & logger
├── config/             # Configuration & Pydantic schemas
├── frontend/           # React frontend application
├── tests/              # Automated unit and integration test suite
├── main.py             # FastAPI server entry point
├── render.yaml         # Cloud deployment specification
└── pyproject.toml      # Project metadata & dependencies
```

## API Capabilities

The platform provides 16 specialized tools for comprehensive stock analysis:
- Stock price tracking (`get_stock_price`)
- Historical data analysis (`get_historical_data`)
- Company stock news (`get_stock_news`)
- Financial statements:
  - Balance Sheet (`get_balance_sheet`)
  - Income Statement (`get_income_statement`)
  - Cash Flow (`get_cash_flow`)
- Company information & ratios (`get_company_info`)
- Dividend history (`get_dividends`)
- Stock split history (`get_splits`)
- Ownership & holder data:
  - Institutional holders (`get_institutional_holders`)
  - Major shareholders (`get_major_shareholders`)
  - Mutual fund holders (`get_mutual_fund_holders`)
- Insider transactions (`get_insider_transactions`)
- Analyst recommendations (`get_analyst_recommendations`)
- Analyst recommendations summary (`get_analyst_recommendations_summary`)
- Company ticker lookup (`get_ticker`)
