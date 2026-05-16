import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Cross-Exchange Crypto Liquidity & Order Flow Engine",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
body { background-color: #10151c; }
.stApp { background-color: #10151c; }
.block-container { padding-top: 2rem; }
h1,h2,h3,h4 { color: #00ffe7; }
.stSidebar { background-color: #181f2a; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("Liquidity Controls")
data_mode = st.sidebar.radio("Data Source", ["Synthetic", "CSV Upload"])
liquidity_type = st.sidebar.selectbox("Liquidity View", ["Bid", "Ask", "Imbalance"])
price_depth_range = st.sidebar.slider("Price Level Range", 1, 40, (5, 35))
time_resolution = st.sidebar.selectbox("Time Resolution", ["10s", "30s", "1m", "5m"])
twap_size = st.sidebar.number_input("TWAP Order Size (units)", min_value=10, value=500, step=50)

# ── Data generation ───────────────────────────────────────────────────────────
def generate_synthetic_order_book(num_snapshots=60, num_levels=40, price_start=20000, tick=5):
    times = [datetime.now() + timedelta(seconds=i * 10) for i in range(num_snapshots)]
    prices = np.arange(price_start, price_start + num_levels * tick, tick)
    rows = []
    prev_bid = np.abs(np.random.lognormal(mean=4.5, sigma=0.6, size=num_levels))
    prev_ask = np.abs(np.random.lognormal(mean=4.5, sigma=0.6, size=num_levels))
    for t in times:
        noise_bid = np.random.normal(0, 0.05, num_levels)
        noise_ask = np.random.normal(0, 0.05, num_levels)
        bid_depth = np.clip(prev_bid * (1 + noise_bid), 1, None)
        ask_depth = np.clip(prev_ask * (1 + noise_ask), 1, None)
        # Occasional liquidity gaps
        gaps = np.random.choice(num_levels, size=np.random.randint(1, 4), replace=False)
        ask_depth[gaps] *= np.random.uniform(0.05, 0.25, size=gaps.shape)
        bid_depth[gaps] *= np.random.uniform(0.05, 0.25, size=gaps.shape)
        prev_bid, prev_ask = bid_depth.copy(), ask_depth.copy()
        for i, p in enumerate(prices):
            rows.append({"time": t, "price": p, "bid_depth": bid_depth[i], "ask_depth": ask_depth[i]})
    return pd.DataFrame(rows)


if data_mode == "Synthetic":
    df = generate_synthetic_order_book()
else:
    uploaded = st.sidebar.file_uploader("Upload Order Book CSV", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded, parse_dates=["time"])
    else:
        st.warning("Upload a CSV file.")
        st.stop()

# ── Filtering and aggregation ─────────────────────────────────────────────────
prices_all = np.sort(df["price"].unique())
selected_prices = prices_all[price_depth_range[0]: price_depth_range[1]]
df = df[df["price"].isin(selected_prices)]

time_map = {"10s": 10, "30s": 30, "1m": 60, "5m": 300}
df["time_bin"] = (df["time"].astype(np.int64) // (time_map[time_resolution] * 1_000_000_000)).astype(int)

grouped = df.groupby(["time_bin", "price"]).agg({"bid_depth": "sum", "ask_depth": "sum"}).reset_index()
grouped["imbalance"] = grouped["bid_depth"] - grouped["ask_depth"]
grouped["imbalance_ratio"] = grouped["bid_depth"] / (grouped["ask_depth"] + 1e-6)
grouped["liquidity_concentration"] = (
    grouped["imbalance"].abs() / (grouped["bid_depth"] + grouped["ask_depth"] + 1e-6)
)

# ── TWAP impact estimator ─────────────────────────────────────────────────────
def estimate_twap_cost(df_latest: pd.DataFrame, order_size: float) -> dict:
    """Estimates execution cost of a TWAP buy order split evenly across all available ask levels."""
    ask_df = df_latest[["price", "ask_depth"]].sort_values("price")
    remaining = order_size
    total_cost = 0.0
    mid = (df_latest["price"].min() + df_latest["price"].max()) / 2
    for _, row in ask_df.iterrows():
        fill = min(row["ask_depth"], remaining)
        total_cost += (row["price"] - mid) * fill
        remaining -= fill
        if remaining <= 0:
            break
    avg_slippage = total_cost / (order_size - remaining) if (order_size - remaining) > 0 else 0
    fill_pct = (order_size - remaining) / order_size
    return {"avg_slippage_per_unit": round(avg_slippage, 4),
            "fill_fraction": round(fill_pct, 4),
            "unfilled_units": round(remaining, 2)}


latest_bin = grouped["time_bin"].max()
latest_df = grouped[grouped["time_bin"] == latest_bin]
twap_result = estimate_twap_cost(latest_df, twap_size)

# ── Bid/ask pressure ratio time series ────────────────────────────────────────
pressure_ts = grouped.groupby("time_bin").apply(
    lambda g: g["bid_depth"].sum() / (g["ask_depth"].sum() + 1e-6)
).reset_index(name="pressure_ratio")

# ── Header metrics ────────────────────────────────────────────────────────────
st.title("Cross-Exchange Crypto Liquidity & Order Flow Engine")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Bid Liquidity", f"{latest_df['bid_depth'].sum():,.0f}")
col2.metric("Total Ask Liquidity", f"{latest_df['ask_depth'].sum():,.0f}")
col3.metric("Imbalance", f"{latest_df['imbalance'].sum():,.0f}")
col4.metric("TWAP Slippage/unit", f"{twap_result['avg_slippage_per_unit']:.4f}")
col5.metric("TWAP Fill %", f"{twap_result['fill_fraction']:.0%}")

# ── 3D Liquidity Surface ──────────────────────────────────────────────────────
col_map = {"Bid": "bid_depth", "Ask": "ask_depth", "Imbalance": "imbalance"}
col_name = col_map[liquidity_type]
pivot = grouped.pivot_table(index="price", columns="time_bin", values=col_name, aggfunc="sum").fillna(0)
X, Y = np.meshgrid(pivot.columns, pivot.index)
Z = pivot.values

fig3d = go.Figure(go.Surface(
    x=X, y=Y, z=Z,
    colorscale=[[0, "#0ff"], [0.5, "#00ffe7"], [1, "#ff00ea"]],
    opacity=0.95,
    lighting=dict(ambient=0.7, diffuse=0.8, specular=0.5),
    contours={"z": {"show": True, "color": "#00ffe7"}},
    hovertemplate="Time: %{x}<br>Price: %{y}<br>Liquidity: %{z:.2f}<extra></extra>",
))
fig3d.update_layout(
    title=f"3D Liquidity Surface ({liquidity_type})",
    paper_bgcolor="#10151c", font=dict(color="#00ffe7"),
    scene=dict(xaxis_title="Time Bin", yaxis_title="Price", zaxis_title="Liquidity",
               xaxis=dict(backgroundcolor="#181f2a", color="#00ffe7"),
               yaxis=dict(backgroundcolor="#181f2a", color="#00ffe7"),
               zaxis=dict(backgroundcolor="#181f2a", color="#00ffe7"),
               camera=dict(eye=dict(x=1.5, y=1.5, z=1.2)),
               aspectmode="manual", aspectratio=dict(x=2, y=1, z=0.7)),
    margin=dict(l=0, r=0, t=60, b=0), height=600,
)
st.plotly_chart(fig3d, use_container_width=True)

# ── Bid/Ask Pressure Ratio ────────────────────────────────────────────────────
col_left, col_right = st.columns(2)
with col_left:
    fig_pres = go.Figure()
    fig_pres.add_trace(go.Scatter(
        x=pressure_ts["time_bin"], y=pressure_ts["pressure_ratio"],
        mode="lines", line=dict(color="#00ffe7", width=2), name="Bid/Ask Pressure"
    ))
    fig_pres.add_hline(y=1, line_color="#555", line_width=0.8)
    fig_pres.add_hrect(y0=0, y1=1, fillcolor="rgba(255,0,234,0.05)", line_width=0)
    fig_pres.add_hrect(y0=1, y1=pressure_ts["pressure_ratio"].max() * 1.1,
                       fillcolor="rgba(0,255,231,0.05)", line_width=0)
    fig_pres.update_layout(title="Bid/Ask Pressure Ratio Over Time",
                           paper_bgcolor="#10151c", plot_bgcolor="#10151c",
                           font=dict(color="#00ffe7"), height=380,
                           xaxis_title="Time Bin", yaxis_title="Bid/Ask Ratio",
                           margin=dict(l=0, r=0, b=0, t=40))
    st.plotly_chart(fig_pres, use_container_width=True)

with col_right:
    # Imbalance heatmap
    pivot_imb = grouped.pivot_table(index="price", columns="time_bin", values="imbalance", aggfunc="sum").fillna(0)
    max_abs = np.max(np.abs(pivot_imb.values))
    fig_heat = go.Figure(go.Heatmap(
        z=pivot_imb.values, x=pivot_imb.columns, y=pivot_imb.index,
        colorscale=[[0, "#ff00ea"], [0.5, "#181f2a"], [1, "#00ffe7"]],
        zmin=-max_abs, zmax=max_abs,
        colorbar=dict(title="Imbalance"),
        hovertemplate="Time: %{x}<br>Price: %{y}<br>Imbalance: %{z:.2f}<extra></extra>",
    ))
    fig_heat.update_layout(title="Order Book Imbalance Heatmap",
                           paper_bgcolor="#10151c", plot_bgcolor="#10151c",
                           font=dict(color="#00ffe7"), height=380,
                           xaxis_title="Time Bin", yaxis_title="Price",
                           margin=dict(l=0, r=0, b=0, t=40))
    st.plotly_chart(fig_heat, use_container_width=True)

# ── TWAP detail ───────────────────────────────────────────────────────────────
with st.expander("TWAP Execution Impact Detail"):
    st.json(twap_result)
    st.caption(f"Estimated impact of a {twap_size}-unit market buy at current depth.")

st.caption("Cross-Exchange Crypto Liquidity & Order Flow Engine — market microstructure analytics.")
