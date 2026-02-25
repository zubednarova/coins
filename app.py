import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crypto Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Outfit:wght@300;400;600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
    background-color: #0a0a0f;
    color: #e8e8f0;
  }
  .stApp { background: #0a0a0f; }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background: #111118 !important;
    border-right: 1px solid #1e1e2e;
  }

  /* Metric cards */
  [data-testid="stMetric"] {
    background: #111118;
    border: 1px solid #1e1e2e;
    border-radius: 12px;
    padding: 20px 24px;
    transition: border-color 0.2s;
  }
  [data-testid="stMetric"]:hover { border-color: #f7931a; }
  [data-testid="stMetricLabel"] { color: #888 !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 0.08em; }
  [data-testid="stMetricValue"] { color: #e8e8f0 !important; font-family: 'Space Mono', monospace !important; font-size: 1.6rem !important; }
  [data-testid="stMetricDelta"] { font-family: 'Space Mono', monospace !important; font-size: 0.85rem !important; }

  /* Header */
  h1 { font-family: 'Space Mono', monospace !important; color: #f7931a !important; font-size: 1.8rem !important; }
  h2, h3 { font-family: 'Outfit', sans-serif !important; color: #c8c8d8 !important; }

  /* Plotly charts bg */
  .js-plotly-plot { border-radius: 12px; }

  /* Select boxes */
  [data-testid="stSelectbox"] > div > div {
    background: #1a1a24 !important;
    border: 1px solid #2a2a3e !important;
    color: #e8e8f0 !important;
    border-radius: 8px !important;
  }

  /* Date input */
  [data-testid="stDateInput"] input {
    background: #1a1a24 !important;
    border: 1px solid #2a2a3e !important;
    color: #e8e8f0 !important;
    border-radius: 8px !important;
  }

  /* Divider */
  hr { border-color: #1e1e2e; margin: 1.5rem 0; }

  /* Coin badge */
  .coin-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    margin-left: 8px;
  }
  .btc-badge { background: rgba(247,147,26,0.15); color: #f7931a; border: 1px solid rgba(247,147,26,0.3); }
  .eth-badge { background: rgba(98,126,234,0.15); color: #627eea; border: 1px solid rgba(98,126,234,0.3); }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
COINS = {
    "Bitcoin": {"id": "bitcoin", "symbol": "BTC", "color": "#f7931a"},
    "Ethereum": {"id": "ethereum", "symbol": "ETH", "color": "#627eea"},
}
CURRENCIES = {"USD": "usd", "CZK": "czk"}
CURRENCY_SYMBOLS = {"USD": "$", "CZK": "Kč"}

# ── API helpers ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_current_price(coin_id: str, currency: str) -> dict:
    """Fetch current price + 24h change from CoinGecko."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": currency,
        "include_24hr_change": "true",
        "include_24hr_vol": "true",
        "include_market_cap": "true",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get(coin_id, {})
    except Exception as e:
        st.error(f"Failed to fetch price: {e}")
        return {}


@st.cache_data(ttl=300)
def fetch_history(coin_id: str, currency: str, days: int) -> pd.DataFrame:
    """Fetch OHLC history from CoinGecko."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": currency, "days": days, "interval": "daily"}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])
        market_caps = data.get("market_caps", [])

        df = pd.DataFrame(prices, columns=["timestamp", "price"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.date
        df["volume"] = [v[1] for v in volumes]
        df["market_cap"] = [m[1] for m in market_caps]
        df = df.drop(columns=["timestamp"])
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Failed to fetch history: {e}")
        return pd.DataFrame()


# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Filters")
    st.markdown("---")

    selected_coins = st.multiselect(
        "Cryptocurrency",
        options=list(COINS.keys()),
        default=["Bitcoin", "Ethereum"],
    )
    if not selected_coins:
        selected_coins = ["Bitcoin"]

    currency = st.selectbox("Currency", options=["USD", "CZK"], index=0)
    currency_id = CURRENCIES[currency]
    currency_sym = CURRENCY_SYMBOLS[currency]

    st.markdown("---")
    st.markdown("**Date Range**")

    max_date = datetime.today().date()
    min_date = max_date - timedelta(days=365)

    date_from = st.date_input("From", value=max_date - timedelta(days=30), min_value=min_date, max_value=max_date)
    date_to = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

    if date_from > date_to:
        st.warning("'From' date must be before 'To' date.")
        date_from, date_to = date_to, date_from

    days_diff = (max_date - date_from).days + 1
    days_diff = max(days_diff, 2)

    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("""
    <div style='margin-top:2rem; color:#444; font-size:0.72rem; line-height:1.6;'>
    Data sourced from <strong>CoinGecko API</strong><br>
    Prices refresh every 60s<br>
    History refreshes every 5min
    </div>
    """, unsafe_allow_html=True)


# ── Main content ──────────────────────────────────────────────────────────────
st.markdown("# ₿ Crypto Dashboard")
st.markdown(f"<p style='color:#666; margin-top:-12px; font-size:0.9rem;'>Live prices & historical data · {currency}</p>", unsafe_allow_html=True)
st.markdown("---")

# ── Current prices ────────────────────────────────────────────────────────────
st.markdown("### Live Prices")
cols = st.columns(len(selected_coins) * 3)
col_idx = 0

current_data = {}
for coin_name in selected_coins:
    coin = COINS[coin_name]
    data = fetch_current_price(coin["id"], currency_id)
    current_data[coin_name] = data

    price = data.get(currency_id, 0)
    change_24h = data.get(f"{currency_id}_24h_change", 0)
    vol = data.get(f"{currency_id}_24h_vol", 0)
    mcap = data.get(f"{currency_id}_market_cap", 0)

    badge_cls = "btc-badge" if coin_name == "Bitcoin" else "eth-badge"
    st.markdown(f"""
    <span style='font-family: Space Mono, monospace; font-size:0.9rem; color:#888;'>
      {coin_name}
      <span class='coin-badge {badge_cls}'>{coin["symbol"]}</span>
    </span>
    """, unsafe_allow_html=True)

    c1, c2, c3 = cols[col_idx], cols[col_idx + 1], cols[col_idx + 2]
    with c1:
        st.metric(
            "Price",
            f"{currency_sym}{price:,.2f}" if currency == "USD" else f"{price:,.0f} {currency_sym}",
            delta=f"{change_24h:+.2f}% (24h)",
        )
    with c2:
        vol_fmt = f"{currency_sym}{vol/1e9:.2f}B" if vol > 1e9 else f"{currency_sym}{vol/1e6:.0f}M"
        st.metric("24h Volume", vol_fmt)
    with c3:
        mcap_fmt = f"{currency_sym}{mcap/1e12:.2f}T" if mcap > 1e12 else f"{currency_sym}{mcap/1e9:.1f}B"
        st.metric("Market Cap", mcap_fmt)

    col_idx += 3

st.markdown("---")

# ── Historical charts ─────────────────────────────────────────────────────────
st.markdown("### Price History")

# Fetch & filter history for all selected coins
all_dfs = {}
for coin_name in selected_coins:
    coin = COINS[coin_name]
    df = fetch_history(coin["id"], currency_id, days_diff)
    if not df.empty:
        df = df[(df["date"] >= date_from) & (df["date"] <= date_to)]
        all_dfs[coin_name] = df

# Price chart
if all_dfs:
    fig_price = go.Figure()

    for coin_name, df in all_dfs.items():
        coin = COINS[coin_name]
        # Gradient fill
        fig_price.add_trace(go.Scatter(
            x=df["date"],
            y=df["price"],
            name=coin_name,
            line=dict(color=coin["color"], width=2.5),
            fill="tozeroy",
            fillcolor=f"rgba{tuple(int(coin['color'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (0.07,)}",
            mode="lines",
            hovertemplate=f"<b>{coin_name}</b><br>%{{x}}<br>{currency_sym}%{{y:,.2f}}<extra></extra>",
        ))

    fig_price.update_layout(
        paper_bgcolor="#0a0a0f",
        plot_bgcolor="#0a0a0f",
        font=dict(family="Outfit", color="#888"),
        xaxis=dict(
            gridcolor="#1a1a24",
            showgrid=True,
            zeroline=False,
            tickfont=dict(color="#666"),
        ),
        yaxis=dict(
            gridcolor="#1a1a24",
            showgrid=True,
            zeroline=False,
            tickfont=dict(color="#666"),
            tickprefix=currency_sym if currency == "USD" else "",
            ticksuffix=" Kč" if currency == "CZK" else "",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#aaa"),
        ),
        margin=dict(l=0, r=0, t=20, b=0),
        height=380,
        hovermode="x unified",
    )
    st.plotly_chart(fig_price, use_container_width=True)

# ── Volume chart ──────────────────────────────────────────────────────────────
st.markdown("### Trading Volume")
if all_dfs:
    fig_vol = go.Figure()
    for coin_name, df in all_dfs.items():
        coin = COINS[coin_name]
        fig_vol.add_trace(go.Bar(
            x=df["date"],
            y=df["volume"],
            name=coin_name,
            marker_color=coin["color"],
            opacity=0.75,
            hovertemplate=f"<b>{coin_name}</b><br>%{{x}}<br>{currency_sym}%{{y:,.0f}}<extra></extra>",
        ))

    fig_vol.update_layout(
        paper_bgcolor="#0a0a0f",
        plot_bgcolor="#0a0a0f",
        barmode="group",
        font=dict(family="Outfit", color="#888"),
        xaxis=dict(gridcolor="#1a1a24", tickfont=dict(color="#666")),
        yaxis=dict(gridcolor="#1a1a24", tickfont=dict(color="#666"), tickprefix=currency_sym if currency == "USD" else ""),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#aaa")),
        margin=dict(l=0, r=0, t=20, b=0),
        height=250,
    )
    st.plotly_chart(fig_vol, use_container_width=True)

# ── % Change comparison ───────────────────────────────────────────────────────
if all_dfs and len(all_dfs) >= 1:
    st.markdown("### Relative Performance (indexed to 100)")
    fig_perf = go.Figure()
    for coin_name, df in all_dfs.items():
        coin = COINS[coin_name]
        if len(df) > 1:
            base = df["price"].iloc[0]
            df_indexed = df.copy()
            df_indexed["indexed"] = (df_indexed["price"] / base) * 100
            fig_perf.add_trace(go.Scatter(
                x=df_indexed["date"],
                y=df_indexed["indexed"],
                name=coin_name,
                line=dict(color=coin["color"], width=2),
                mode="lines",
                hovertemplate=f"<b>{coin_name}</b><br>%{{x}}<br>%{{y:.1f}}<extra></extra>",
            ))

    fig_perf.add_hline(y=100, line_dash="dash", line_color="#333", line_width=1)
    fig_perf.update_layout(
        paper_bgcolor="#0a0a0f",
        plot_bgcolor="#0a0a0f",
        font=dict(family="Outfit", color="#888"),
        xaxis=dict(gridcolor="#1a1a24", tickfont=dict(color="#666")),
        yaxis=dict(gridcolor="#1a1a24", tickfont=dict(color="#666")),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#aaa")),
        margin=dict(l=0, r=0, t=20, b=0),
        height=280,
    )
    st.plotly_chart(fig_perf, use_container_width=True)

# ── Stats table ───────────────────────────────────────────────────────────────
st.markdown("### Period Statistics")
if all_dfs:
    stats_rows = []
    for coin_name, df in all_dfs.items():
        if df.empty:
            continue
        pct_change = ((df["price"].iloc[-1] - df["price"].iloc[0]) / df["price"].iloc[0]) * 100
        stats_rows.append({
            "Coin": coin_name,
            "From": str(df["date"].iloc[0]),
            "To": str(df["date"].iloc[-1]),
            f"Open ({currency})": f"{currency_sym}{df['price'].iloc[0]:,.2f}" if currency == "USD" else f"{df['price'].iloc[0]:,.0f} Kč",
            f"Close ({currency})": f"{currency_sym}{df['price'].iloc[-1]:,.2f}" if currency == "USD" else f"{df['price'].iloc[-1]:,.0f} Kč",
            f"High ({currency})": f"{currency_sym}{df['price'].max():,.2f}" if currency == "USD" else f"{df['price'].max():,.0f} Kč",
            f"Low ({currency})": f"{currency_sym}{df['price'].min():,.2f}" if currency == "USD" else f"{df['price'].min():,.0f} Kč",
            "% Change": f"{pct_change:+.2f}%",
        })

    if stats_rows:
        stats_df = pd.DataFrame(stats_rows)
        st.dataframe(
            stats_df,
            use_container_width=True,
            hide_index=True,
        )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(f"""
<div style='text-align:center; color:#333; font-size:0.75rem; padding: 8px 0;'>
  Data provided by <strong style='color:#444'>CoinGecko API</strong> · 
  Last refreshed: {datetime.now().strftime('%H:%M:%S')} ·
  <em>Not financial advice</em>
</div>
""", unsafe_allow_html=True)
