# AI Portfolio Risk Analyzer

## Description
The AI Portfolio Risk Analyzer is an interactive, real-time dashboard built with Streamlit. It allows users to input a custom stock portfolio, dynamically fetches real-time market data via the Yahoo Finance API, and calculates advanced risk metrics (Annualized Return, Volatility, Sharpe Ratio, Max Drawdown). The dashboard also uses OpenAI's GPT models to synthesize these quantitative metrics into actionable, qualitative business insights.

## Features
- **Real-Time Data Integration**: Fetches the latest stock prices and historical data using `yfinance`.
- **Portfolio Grading**: Automatically grades your portfolio A–D based on Sharpe Ratio, diversification, returns, and drawdown.
- **Health Alerts**: Automatically flags concentration risk, high correlation, high beta, and underperforming positions.
- **Advanced Risk Metrics**: Calculates Sharpe ratios, beta, correlation matrices, and a diversification score.
- **What-If Rebalancing Simulator**: Adjust portfolio weights with sliders and instantly see how metrics change.
- **Monte Carlo Simulation**: Projects 500 potential future paths based on historical portfolio volatility.
- **Sector Exposure Analysis**: Visualizes portfolio concentration by sector.
- **Historical Benchmark Reference**: Compares your portfolio against long-term S&P 500 averages (NYU Damodaran, 1928–2024).
- **AI-Powered Analysis**: Leverages OpenAI's GPT to provide specific, ticker-level insights and rebalancing recommendations.
- **Interactive Visualizations**: Uses Plotly to render responsive charts including candlestick, heatmap, and Monte Carlo fan charts.

## Installation

### 1. Clone the repository
```bash
git clone <your-github-repo-url>
cd portfolio-risk-analyzer
```

### 2. Set up environment (Recommended — using Conda)
```bash
conda create -n portfolioanalyzer python=3.11
conda activate portfolioanalyzer
```

Or using a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Mac/Linux
# venv\Scripts\activate  # On Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up your OpenAI API key
You will need an OpenAI API key to use the AI analysis feature.

**Option A — Environment variable (local development):**
```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

**Option B — Streamlit secrets (for Streamlit Cloud deployment):**
Create a file at `.streamlit/secrets.toml`:
```toml
OPENAI_API_KEY = "your_openai_api_key_here"
```

### 5. Run the application
```bash
streamlit run app.py
```
The dashboard will open automatically at `http://localhost:8501`.

## Deployment
This app is deployed on Streamlit Cloud. To deploy your own instance:
1. Push this repository to GitHub (public)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Add your `OPENAI_API_KEY` in the Streamlit Cloud secrets manager
5. Click Deploy

## Tech Stack
- **Frontend/Framework**: Streamlit
- **Data Source**: Yahoo Finance (`yfinance`)
- **AI Model**: OpenAI GPT-5.4-mini
- **Visualizations**: Plotly
- **Data Processing**: Pandas, NumPy
- **IDE**: Google Antigravity

## Disclaimer
This dashboard is for informational and educational purposes only. Data is provided by Yahoo Finance and may be delayed or inaccurate. AI analysis is generated automatically and does not constitute professional financial, legal, or investment advice. Past performance is not indicative of future results. Monte Carlo simulations are based on historical data and do not guarantee future performance. Users rely on this dashboard at their own risk. This tool is not endorsed by the University of North Carolina at Chapel Hill.
