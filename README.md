# Smart Order Routing Backtest

This project implements and compares various order execution strategies—**Best Ask**, **TWAP (Time-Weighted Average Price)**, **VWAP (Volume-Weighted Average Price)**, and a **Smart Order Router (SOR)**—to assess their effectiveness in minimizing trading costs.

## 📊 Strategies Implemented

### ✅ Best Ask
Executes orders by always picking the venue with the lowest available ask price.

### ✅ TWAP (Time-Weighted Average Price)
Spreads the order evenly across time buckets (1-minute intervals) and selects the best price in each bucket.

### ✅ VWAP (Volume-Weighted Average Price)
Distributes orders proportionally to the available volume on each venue.

### ✅ Smart Order Router
Optimizes order allocation across venues by minimizing execution cost and risk, incorporating parameters:
- `lambda_over`: Penalty for overfilling the order.
- `lambda_under`: Penalty for underfilling.
- `theta_queue`: Risk adjustment for queue position.

## 📁 File Structure

- `backtest.py`: Main Python script containing strategy definitions and a `main()` function for testing on sample data (`l1_day.csv`).
- `l1_day.csv`: (Not included) CSV input file expected to contain the following columns:
  - `ts_event` (timestamp)
  - `publisher_id` (venue ID)
  - `ask_px_00` (ask price)
  - `ask_sz_00` (ask size)

## ⚙️ How It Works

The `main()` function:
1. Loads `l1_day.csv`
2. Runs each strategy
3. Compares their results
4. Calculates basis point (bps) savings of Smart Order Routing over others
5. Prints a JSON summary of performance

## 🧪 Example Output

```json
{
    "best_parameters": {
        "lambda_over": 0.05,
        "lambda_under": 0.025,
        "theta_queue": 0.005
    },
    "smart_order_router": {
        "total_cash_spent": 10012.5,
        "avg_fill_price": 2.0025
    },
    "best_ask": {
        "total_cash_spent": 10100.0,
        "avg_fill_price": 2.02
    },
    "twap": {...},
    "vwap": {...},
    "savings_bps": {
        "best_ask": 86.42,
        "twap": 59.88,
        "vwap": 34.71
    }
}
