import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from openai import OpenAI

# Page configuration
st.set_page_config(
    page_title="AI Portfolio Risk Analyzer",
    page_icon="📊",
    layout="wide"
)

# Title
st.title("📊 AI Portfolio Risk Analyzer")
st.markdown("Enter your stock portfolio and get real-time risk analysis powered by AI.")

# Sidebar
st.sidebar.header("Portfolio Setup")
st.sidebar.markdown("Enter 2-8 stock tickers separated by commas.")

tickers_input = st.sidebar.text_input(
    "Stock Tickers",
    value="AAPL, MSFT, GOOGL, AMZN",
    help="Enter ticker symbols separated by commas (e.g. AAPL, MSFT, GOOGL)"
)

tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

if len(tickers) < 2:
    st.warning("Please enter at least 2 stock tickers to analyze portfolio risk.")
    st.stop()

if len(tickers) > 8:
    st.warning("Please enter no more than 8 tickers for best results.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.markdown("**Investment Amount per Stock ($):**")
investment_amounts = {}
for ticker in tickers:
    amount = st.sidebar.number_input(
        f"{ticker} ($)",
        min_value=0,
        max_value=10_000_000,
        value=10_000,
        step=1_000,
        key=f"inv_{ticker}"
    )
    investment_amounts[ticker] = amount

total_investment = sum(investment_amounts.values())

st.sidebar.markdown("---")
period_options = {
    "3 Months": "3mo",
    "6 Months": "6mo",
    "1 Year": "1y",
    "2 Years": "2y",
    "5 Years": "5y"
}
selected_period = st.sidebar.selectbox("Analysis Period", list(period_options.keys()), index=2)
period = period_options[selected_period]

risk_free_rate = st.sidebar.slider(
    "Risk-Free Rate (%) — Use current T-bill rate",
    min_value=0.0,
    max_value=10.0,
    value=4.5,
    step=0.1
) / 100

# Historical S&P 500 reference data (static)
HISTORICAL_SP500 = {
    "10-Year Avg Annual Return": "10.7%",
    "20-Year Avg Annual Return": "9.8%",
    "Historical Avg Volatility": "~15%",
    "Historical Avg Sharpe": "~0.4–0.6",
    "Source": "Damodaran NYU (1928–2024)"
}

# Fetch data
@st.cache_data(ttl=300)
def fetch_portfolio_data(tickers, period):
    data = {}
    info = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            if not hist.empty:
                data[ticker] = hist['Close']
                info[ticker] = stock.info
        except Exception as e:
            st.warning(f"Could not fetch data for {ticker}: {str(e)}")
    return pd.DataFrame(data), info

@st.cache_data(ttl=300)
def fetch_benchmark(period):
    sp500 = yf.Ticker("^GSPC")
    return sp500.history(period=period)['Close']

def calculate_metrics(prices, weights, risk_free_rate):
    returns = prices.pct_change().dropna()
    portfolio_returns = returns.dot(weights)
    ann_return = portfolio_returns.mean() * 252
    ann_volatility = portfolio_returns.std() * np.sqrt(252)
    sharpe = (ann_return - risk_free_rate) / ann_volatility if ann_volatility != 0 else 0
    cumulative = (1 + portfolio_returns).cumprod()
    rolling_max = cumulative.expanding().max()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    individual_volatilities = returns.std() * np.sqrt(252)
    correlation = returns.corr()
    return {
        'ann_return': ann_return,
        'ann_volatility': ann_volatility,
        'sharpe': sharpe,
        'max_drawdown': max_drawdown,
        'portfolio_returns': portfolio_returns,
        'individual_volatilities': individual_volatilities,
        'correlation': correlation,
        'returns': returns
    }

def calculate_diversification_score(correlation_matrix):
    n = len(correlation_matrix)
    if n < 2:
        return 0
    upper = correlation_matrix.where(np.triu(np.ones(correlation_matrix.shape), k=1).astype(bool))
    avg_correlation = upper.stack().mean()
    score = max(0, min(100, (1 - avg_correlation) * 100))
    return score

def get_portfolio_grade(ann_return, ann_volatility, sharpe, diversification_score, max_drawdown):
    score = 0
    if sharpe > 1.5: score += 35
    elif sharpe > 1.0: score += 25
    elif sharpe > 0.5: score += 15
    else: score += 5
    if diversification_score > 70: score += 25
    elif diversification_score > 50: score += 15
    else: score += 5
    if ann_return > 0.15: score += 25
    elif ann_return > 0.08: score += 15
    else: score += 5
    if max_drawdown > -0.15: score += 15
    elif max_drawdown > -0.30: score += 10
    else: score += 3
    if score >= 85: return "A", "Excellent risk-adjusted portfolio", "🟢"
    elif score >= 70: return "B", "Good portfolio with room to improve", "🟡"
    elif score >= 55: return "C", "Average portfolio — consider rebalancing", "🟠"
    else: return "D", "High risk portfolio — significant improvements needed", "🔴"

def generate_flags(ann_return, ann_volatility, sharpe, max_drawdown,
                   diversification_score, avg_correlation, weights,
                   valid_tickers, sectors, betas, individual_returns, corr_matrix):
    flags = []

    # Concentration risk
    sector_weights = {}
    for t, w in zip(valid_tickers, weights):
        s = sectors.get(t, 'Unknown')
        sector_weights[s] = sector_weights.get(s, 0) + w
    for sector, w in sector_weights.items():
        if w > 0.5:
            flags.append(("🔴 High Sector Concentration",
                          f"{sector} makes up {w*100:.0f}% of your portfolio. Consider diversifying into other sectors."))

    # Single stock dominance
    for t, w in zip(valid_tickers, weights):
        if w > 0.4:
            flags.append(("🔴 Single Stock Overweight",
                          f"{t} makes up {w*100:.0f}% of your portfolio. Consider trimming this position."))

    # High correlation pairs
    for i in range(len(valid_tickers)):
        for j in range(i+1, len(valid_tickers)):
            c = corr_matrix.iloc[i, j]
            if c > 0.75:
                flags.append(("🟡 High Correlation Detected",
                              f"{valid_tickers[i]} and {valid_tickers[j]} have a correlation of {c:.2f}. They may move together, reducing diversification benefit."))

    # High beta
    for t in valid_tickers:
        b = betas.get(t)
        if isinstance(b, float) and b > 1.5:
            flags.append(("🟡 High Market Sensitivity",
                          f"{t} has a beta of {b:.2f}, meaning it moves {b:.1f}x the market. This increases downside risk in market downturns."))

    # Poor Sharpe
    if sharpe < 0.5:
        flags.append(("🔴 Poor Risk-Adjusted Return",
                      f"Your Sharpe Ratio of {sharpe:.2f} is below 0.5. You are not being adequately compensated for the risk you're taking."))

    # Large drawdown
    if max_drawdown < -0.25:
        flags.append(("🔴 Large Maximum Drawdown",
                      f"Your portfolio has experienced a drawdown of {max_drawdown*100:.1f}%. This level of loss may be difficult to recover from."))

    # Underperforming stocks
    for t in valid_tickers:
        r = individual_returns.get(t, 0)
        if r < -10:
            flags.append(("🟡 Underperforming Position",
                          f"{t} has returned {r:.1f}% this period. Consider reviewing whether this position still fits your strategy."))

    if not flags:
        flags.append(("🟢 No Major Issues Detected",
                      "Your portfolio looks healthy based on the current metrics. Continue to monitor regularly."))

    return flags

def run_monte_carlo(portfolio_returns, n_simulations=500, n_days=252):
    mean_return = portfolio_returns.mean()
    std_return = portfolio_returns.std()
    simulations = []
    for _ in range(n_simulations):
        daily_returns = np.random.normal(mean_return, std_return, n_days)
        cumulative = (1 + daily_returns).cumprod() * 100
        simulations.append(cumulative)
    return np.array(simulations)

@st.cache_data(ttl=600)
def get_ai_portfolio_analysis(tickers, weights, ann_return, ann_volatility, sharpe,
                               max_drawdown, diversification_score, avg_correlation,
                               period, sectors, betas, individual_returns,
                               total_investment, investment_amounts, grade):
    try:
        client = OpenAI()
        portfolio_str = ", ".join([f"{t} ({w*100:.1f}%, ${investment_amounts.get(t, 0):,})"
                                   for t, w in zip(tickers, weights)])
        sector_str = ", ".join([f"{t}: {sectors.get(t, 'N/A')}" for t in tickers])
        beta_str = ", ".join([f"{t}: {betas.get(t, 'N/A')}" for t in tickers])
        returns_str = ", ".join([f"{t}: {individual_returns.get(t, 0):.1f}%" for t in tickers])

        prompt = f"""
        You are analyzing a real investment portfolio. Provide deep, specific insights.

        PORTFOLIO: {portfolio_str}
        Total Investment: ${total_investment:,}
        Period: {period}
        Portfolio Grade: {grade}

        METRICS:
        - Annualized Return: {ann_return*100:.2f}% (S&P 500 avg: ~10.7%)
        - Annualized Volatility: {ann_volatility*100:.2f}% (S&P 500 avg: ~15%)
        - Sharpe Ratio: {sharpe:.2f} (S&P 500 avg: ~0.4–0.6)
        - Max Drawdown: {max_drawdown*100:.2f}%
        - Diversification Score: {diversification_score:.0f}/100
        - Avg Correlation: {avg_correlation:.2f}

        INDIVIDUAL DATA:
        - Sectors: {sector_str}
        - Betas: {beta_str}
        - Returns: {returns_str}

        Provide:
        1. **Overall Assessment**: Compare risk/return to S&P 500 with specific numbers.
        2. **Diversification Analysis**: Comment on sector concentration, name specific stocks.
        3. **Biggest Winners & Laggards**: Call out best and worst performers by name.
        4. **Key Risks**: Top 2 risks specific to this portfolio — mention actual tickers.
        5. **Actionable Recommendations**: 3 concrete suggestions with specific tickers and percentages.

        Be direct, specific, use actual ticker names and numbers throughout.
        Under 500 words.
        End with: "This is AI-generated analysis for informational purposes only and does not constitute professional financial advice."
        """

        response = client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": "You are a senior portfolio risk analyst. Be specific, reference actual tickers and numbers. Never give generic advice."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI analysis unavailable: {str(e)}"

# ── Fetch Data ──
with st.spinner("Fetching real-time market data..."):
    prices, stock_info = fetch_portfolio_data(tuple(tickers), period)
    benchmark = fetch_benchmark(period)

valid_tickers = list(prices.columns)
if len(valid_tickers) < 2:
    st.error("Could not fetch data for enough tickers. Please check your ticker symbols.")
    st.stop()

valid_investments = {t: investment_amounts.get(t, 10000) for t in valid_tickers}
total_valid = sum(valid_investments.values())
if total_valid == 0:
    weights = np.array([1/len(valid_tickers)] * len(valid_tickers))
else:
    weights = np.array([valid_investments[t] / total_valid for t in valid_tickers])

metrics = calculate_metrics(prices, weights, risk_free_rate)
diversification_score = calculate_diversification_score(metrics['correlation'])

corr_matrix = metrics['correlation']
upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
avg_correlation = upper.stack().mean()

sectors = {t: stock_info.get(t, {}).get('sector', 'N/A') for t in valid_tickers}
betas = {t: round(stock_info.get(t, {}).get('beta', 0), 2) if stock_info.get(t, {}).get('beta') else 'N/A' for t in valid_tickers}
individual_returns = {t: (prices[t].iloc[-1] / prices[t].iloc[0] - 1) * 100 for t in valid_tickers}

grade, grade_desc, grade_emoji = get_portfolio_grade(
    metrics['ann_return'], metrics['ann_volatility'],
    metrics['sharpe'], diversification_score, metrics['max_drawdown']
)

# ── Section 1: Portfolio Grade ──
st.subheader("🎯 Portfolio Grade")
gcol1, gcol2 = st.columns([1, 4])
with gcol1:
    st.markdown(f"<h1 style='font-size: 80px; text-align: center;'>{grade_emoji} {grade}</h1>", unsafe_allow_html=True)
with gcol2:
    st.markdown(f"### {grade_desc}")
    st.markdown("Your portfolio is scored based on Sharpe Ratio, diversification, returns, and drawdown relative to historical benchmarks.")

st.markdown("---")

# ── Section 2: Flags & Alerts ──
st.subheader("🚨 Portfolio Health Alerts")

flags = generate_flags(
    metrics['ann_return'], metrics['ann_volatility'], metrics['sharpe'],
    metrics['max_drawdown'], diversification_score, avg_correlation,
    weights, valid_tickers, sectors, betas, individual_returns, corr_matrix
)

for title, message in flags:
    if "🔴" in title:
        st.error(f"**{title}** — {message}")
    elif "🟡" in title:
        st.warning(f"**{title}** — {message}")
    else:
        st.success(f"**{title}** — {message}")

st.markdown("---")

# ── Section 3: Key Metrics ──
st.subheader("📈 Portfolio Risk Metrics")

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Total Invested", f"${total_valid:,.0f}")
col2.metric("Annualized Return", f"{metrics['ann_return']*100:.2f}%",
            delta="Above S&P avg" if metrics['ann_return'] > 0.107 else "Below S&P avg")
col3.metric("Annualized Volatility", f"{metrics['ann_volatility']*100:.2f}%")
col4.metric("Sharpe Ratio", f"{metrics['sharpe']:.2f}",
            delta="Good" if metrics['sharpe'] > 1 else "Needs improvement")
col5.metric("Max Drawdown", f"{metrics['max_drawdown']*100:.2f}%")
col6.metric("Diversification Score", f"{diversification_score:.0f}/100",
            delta="Well diversified" if diversification_score > 60 else "Poorly diversified")

st.markdown("---")

# ── Section 4: Historical Context ──
st.subheader("📚 Historical S&P 500 Benchmark Reference")
st.markdown("*Static reference data — long-term S&P 500 averages (Source: NYU Damodaran, 1928–2024)*")

hcol1, hcol2, hcol3, hcol4 = st.columns(4)
hcol1.metric("S&P 500 10-Year Avg Return", HISTORICAL_SP500["10-Year Avg Annual Return"])
hcol2.metric("S&P 500 20-Year Avg Return", HISTORICAL_SP500["20-Year Avg Annual Return"])
hcol3.metric("Historical Avg Volatility", HISTORICAL_SP500["Historical Avg Volatility"])
hcol4.metric("Historical Avg Sharpe", HISTORICAL_SP500["Historical Avg Sharpe"])

st.markdown("---")

# ── Section 5: Portfolio vs Benchmark ──
st.subheader("📊 Portfolio Performance vs S&P 500")

normalized_portfolio = (1 + metrics['portfolio_returns']).cumprod() * 100
benchmark_aligned = benchmark.reindex(normalized_portfolio.index, method='ffill')
benchmark_returns = benchmark_aligned.pct_change().dropna()
normalized_benchmark = (1 + benchmark_returns).cumprod() * 100

fig_perf = go.Figure()
fig_perf.add_trace(go.Scatter(x=normalized_portfolio.index, y=normalized_portfolio.values,
                               name="Your Portfolio", line=dict(color='#00CC96', width=2)))
fig_perf.add_trace(go.Scatter(x=normalized_benchmark.index, y=normalized_benchmark.values,
                               name="S&P 500", line=dict(color='#EF553B', width=2, dash='dash')))
fig_perf.update_layout(height=400, template='plotly_dark',
                        yaxis_title="Portfolio Value (Starting = 100)", xaxis_title="Date",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_perf, width="stretch")

st.markdown("---")

# ── Section 6: Allocation + Sector Exposure ──
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🥧 Portfolio Allocation")
    pie_fig = px.pie(values=weights * 100, names=valid_tickers,
                     template='plotly_dark', hole=0.4)
    pie_fig.update_layout(height=350)
    st.plotly_chart(pie_fig, width="stretch")

with col_right:
    st.subheader("🏭 Sector Exposure")
    sector_weights = {}
    for t, w in zip(valid_tickers, weights):
        s = sectors.get(t, 'Unknown')
        sector_weights[s] = sector_weights.get(s, 0) + w * 100

    sector_df = pd.DataFrame({
        'Sector': list(sector_weights.keys()),
        'Weight (%)': list(sector_weights.values())
    }).sort_values('Weight (%)', ascending=True)

    fig_sector = px.bar(sector_df, x='Weight (%)', y='Sector', orientation='h',
                         color='Weight (%)', color_continuous_scale='Blues',
                         template='plotly_dark')
    fig_sector.update_layout(height=350)
    st.plotly_chart(fig_sector, width="stretch")

st.markdown("---")

# ── Section 7: What-If Rebalancing Simulator ──
st.subheader("🔧 What-If Rebalancing Simulator")
st.markdown("Adjust weights below to simulate how rebalancing would affect your risk metrics.")

sim_weights = []
sim_cols = st.columns(len(valid_tickers))
for i, ticker in enumerate(valid_tickers):
    default_w = int(round(weights[i] * 100))
    w = sim_cols[i].slider(f"{ticker} %", 0, 100, default_w, step=5, key=f"sim_{ticker}")
    sim_weights.append(w)

total_sim = sum(sim_weights)

if total_sim == 0:
    st.warning("Total weight is 0%. Please adjust the sliders.")
else:
    normalized_sim_weights = np.array([w / total_sim for w in sim_weights])

    if total_sim != 100:
        st.info(f"Weights sum to {total_sim}% — automatically normalized to 100%.")

    sim_metrics = calculate_metrics(prices, normalized_sim_weights, risk_free_rate)
    sim_div = calculate_diversification_score(sim_metrics['correlation'])
    sim_grade, sim_grade_desc, sim_emoji = get_portfolio_grade(
        sim_metrics['ann_return'], sim_metrics['ann_volatility'],
        sim_metrics['sharpe'], sim_div, sim_metrics['max_drawdown']
    )

    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    sc1.metric("Simulated Return", f"{sim_metrics['ann_return']*100:.2f}%",
               delta=f"{(sim_metrics['ann_return'] - metrics['ann_return'])*100:.2f}% vs current")
    sc2.metric("Simulated Volatility", f"{sim_metrics['ann_volatility']*100:.2f}%",
               delta=f"{(sim_metrics['ann_volatility'] - metrics['ann_volatility'])*100:.2f}% vs current")
    sc3.metric("Simulated Sharpe", f"{sim_metrics['sharpe']:.2f}",
               delta=f"{sim_metrics['sharpe'] - metrics['sharpe']:.2f} vs current")
    sc4.metric("Simulated Max Drawdown", f"{sim_metrics['max_drawdown']*100:.2f}%")
    sc5.metric("Simulated Grade", f"{sim_emoji} {sim_grade}", delta=sim_grade_desc)

st.markdown("---")

# ── Section 8: Monte Carlo ──
st.subheader("🎲 Monte Carlo Simulation — 1-Year Outlook")
st.markdown("500 simulated portfolio paths based on historical return and volatility. Shows range of possible outcomes.")

mc_results = run_monte_carlo(metrics['portfolio_returns'], n_simulations=500, n_days=252)

p10 = np.percentile(mc_results, 10, axis=0)
p50 = np.percentile(mc_results, 50, axis=0)
p90 = np.percentile(mc_results, 90, axis=0)

fig_mc = go.Figure()

# Sample of individual paths
for i in range(0, 500, 10):
    fig_mc.add_trace(go.Scatter(
        y=mc_results[i],
        mode='lines',
        line=dict(color='rgba(100, 149, 237, 0.1)', width=1),
        showlegend=False
    ))

fig_mc.add_trace(go.Scatter(y=p90, name='90th Percentile (Best Case)',
                             line=dict(color='#00CC96', width=2)))
fig_mc.add_trace(go.Scatter(y=p50, name='50th Percentile (Median)',
                             line=dict(color='white', width=2)))
fig_mc.add_trace(go.Scatter(y=p10, name='10th Percentile (Worst Case)',
                             line=dict(color='#EF553B', width=2)))

fig_mc.update_layout(
    height=450, template='plotly_dark',
    yaxis_title="Portfolio Value (Starting = 100)",
    xaxis_title="Trading Days",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig_mc, width="stretch")

mc_final = mc_results[:, -1]
mc1, mc2, mc3 = st.columns(3)
mc1.metric("Worst Case (10th %ile)", f"{p10[-1]:.1f}",
           delta=f"{p10[-1]-100:.1f}% from start")
mc2.metric("Median Outcome (50th %ile)", f"{p50[-1]:.1f}",
           delta=f"{p50[-1]-100:.1f}% from start")
mc3.metric("Best Case (90th %ile)", f"{p90[-1]:.1f}",
           delta=f"{p90[-1]-100:.1f}% from start")

st.markdown("---")

# ── Section 9: Correlation Heatmap ──
st.subheader("🔥 Stock Correlation Heatmap")
st.markdown("Correlation measures how stocks move together. Lower correlation = better diversification.")

fig_corr = px.imshow(metrics['correlation'], text_auto=".2f",
                      color_continuous_scale='RdBu_r', zmin=-1, zmax=1, aspect='auto')
fig_corr.update_layout(height=400, template='plotly_dark')
st.plotly_chart(fig_corr, width="stretch")

st.markdown("---")

# ── Section 10: Individual Volatility + Returns ──
col_v, col_r = st.columns(2)

with col_v:
    st.subheader("⚡ Individual Stock Volatility")
    vol_df = pd.DataFrame({
        'Ticker': valid_tickers,
        'Annualized Volatility (%)': (metrics['individual_volatilities'] * 100).values
    }).sort_values('Annualized Volatility (%)', ascending=True)
    fig_vol = px.bar(vol_df, x='Annualized Volatility (%)', y='Ticker', orientation='h',
                      color='Annualized Volatility (%)', color_continuous_scale='RdYlGn_r',
                      template='plotly_dark')
    fig_vol.update_layout(height=300)
    st.plotly_chart(fig_vol, width="stretch")

with col_r:
    st.subheader("📉 Individual Stock Returns")
    returns_df = pd.DataFrame({
        'Ticker': valid_tickers,
        'Total Return (%)': [individual_returns[t] for t in valid_tickers]
    }).sort_values('Total Return (%)', ascending=True)
    fig_returns = px.bar(returns_df, x='Total Return (%)', y='Ticker', orientation='h',
                          color='Total Return (%)', color_continuous_scale='RdYlGn',
                          template='plotly_dark')
    fig_returns.update_layout(height=300)
    st.plotly_chart(fig_returns, width="stretch")

st.markdown("---")

# ── Section 11: AI Analysis ──
st.subheader("🤖 AI Portfolio Analysis")

with st.spinner("Generating AI portfolio analysis..."):
    ai_analysis = get_ai_portfolio_analysis(
        tickers=tuple(valid_tickers),
        weights=tuple(weights),
        ann_return=metrics['ann_return'],
        ann_volatility=metrics['ann_volatility'],
        sharpe=metrics['sharpe'],
        max_drawdown=metrics['max_drawdown'],
        diversification_score=diversification_score,
        avg_correlation=float(avg_correlation),
        period=selected_period,
        sectors=sectors,
        betas=betas,
        individual_returns=individual_returns,
        total_investment=total_valid,
        investment_amounts=investment_amounts,
        grade=grade
    )

st.info(ai_analysis)

st.markdown("---")

# ── Section 12: Holdings Summary ──
st.subheader("📋 Portfolio Holdings Summary")

holdings_data = []
for ticker, weight in zip(valid_tickers, weights):
    info = stock_info.get(ticker, {})
    holdings_data.append({
        'Ticker': ticker,
        'Company': info.get('longName', ticker),
        'Sector': info.get('sector', 'N/A'),
        'Weight': f"{weight*100:.1f}%",
        'Invested': f"${valid_investments[ticker]:,}",
        'Current Price': f"${prices[ticker].iloc[-1]:.2f}",
        'Period Return': f"{individual_returns[ticker]:.1f}%",
        'Market Cap': f"${info.get('marketCap', 0)/1e9:.1f}B" if info.get('marketCap') else 'N/A',
        'P/E Ratio': f"{info.get('trailingPE', 'N/A'):.1f}" if isinstance(info.get('trailingPE'), float) else 'N/A',
        'Beta': f"{info.get('beta', 'N/A'):.2f}" if isinstance(info.get('beta'), float) else 'N/A'
    })

st.dataframe(pd.DataFrame(holdings_data), width="stretch")

# ── Footer ──
st.markdown("---")
st.markdown("""
⚠️ **Disclaimer:** This dashboard is for informational and educational purposes only. 
Data is provided by Yahoo Finance and may be delayed or inaccurate. 
AI analysis is generated automatically and does not constitute professional financial, 
legal, or investment advice. Past performance is not indicative of future results.
Monte Carlo simulations are based on historical data and do not guarantee future performance.
Users rely on this dashboard at their own risk. 
This tool is not endorsed by the University of North Carolina at Chapel Hill.
""")