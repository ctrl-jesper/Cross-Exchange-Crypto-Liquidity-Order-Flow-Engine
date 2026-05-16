# Cross-Exchange Crypto Liquidity & Order Flow Engine

Interactive market microstructure analysis platform for cryptocurrency order book data. Renders a 3D liquidity depth surface across price levels and time, tracks bid/ask pressure ratio dynamics, and estimates the market impact of a TWAP execution at current book depth.

## What it does

- Generates realistic synthetic order book snapshots (log-normal depth, random liquidity gaps) or accepts CSV upload
- Aggregates order book data by configurable time resolution (10s to 5m)
- Renders a 3D surface of bid depth, ask depth, or order imbalance across price and time
- Tracks the bid/ask pressure ratio over time — a directional flow signal
- Renders an order book imbalance heatmap (price × time)
- Estimates TWAP execution cost: average slippage per unit and fill fraction for a given order size

## Panels

| Panel | Content |
|---|---|
| 3D Liquidity Surface | Bid, ask, or imbalance depth rendered as a 3D surface |
| Bid/Ask Pressure Ratio | Time series of total bid volume / total ask volume |
| Imbalance Heatmap | Price × time heatmap of order imbalance |
| TWAP Detail | Slippage estimate for a configurable market buy order |

## Installation

```bash
git clone https://github.com/jespermathiasnielsen/Cross-Exchange-Crypto-Liquidity-Order-Flow-Engine.git
cd Cross-Exchange-Crypto-Liquidity-Order-Flow-Engine
pip install -r requirements.txt
```

## Usage

```bash
streamlit run src/app.py
```

Open http://localhost:8501 in your browser.

## CSV format

To upload real order book data, provide a CSV with the following columns:

| Column | Type | Description |
|---|---|---|
| `time` | datetime | Snapshot timestamp |
| `price` | float | Price level |
| `bid_depth` | float | Resting bid volume at this price level |
| `ask_depth` | float | Resting ask volume at this price level |

## TWAP impact methodology

The TWAP estimator models a market buy order executed against resting ask levels in price-ascending order. Slippage is computed as the volume-weighted average price deviation from mid. This is a simplified model — it does not account for order replenishment, adverse selection, or market impact feedback.

## Bid/Ask Pressure Ratio

Values above 1 indicate more bid liquidity than ask — a bullish order book lean. Values below 1 indicate more ask liquidity — a bearish lean. Sustained pressure in one direction can precede directional price moves, particularly when accompanied by large imbalance in the top price levels.

## Synthetic data

The synthetic order book uses log-normal volume distributions (consistent with empirical crypto microstructure research) and introduces random liquidity gaps to simulate the thin zones that appear near support and resistance levels in real books.

## License

MIT
