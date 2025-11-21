# Portfolio Time Series Guide

## Overview

The portfolio calculator now generates **historical time series** showing how portfolio value has changed over time, enabling:
- Track portfolio performance over days/months/years
- Analyze daily and monthly returns
- View cumulative returns from inception
- Identify best/worst performing days

## New Features

### 1. **Portfolio Time Series**
Shows daily portfolio value based on current holdings and historical NAVs.

### 2. **Monthly Returns**
Aggregated monthly performance with best/worst days.

### 3. **Cumulative Returns**
Tracks portfolio growth from start date.

## Usage

### Generate Time Series Report

```bash
python3 portfolio_calculator.py CLIENT123
```

**Output Files:**
- `portfolio_timeseries_CLIENT123.csv` - Daily values
- `portfolio_monthly_CLIENT123.csv` - Monthly returns
- `portfolio_holdings_CLIENT123.csv` - Current holdings

**Console Output:**
```
============================================================
Portfolio Summary for CLIENT123
============================================================
  Total Holdings: 5
  Total Invested: ₹5,00,000.00
  Current Value: ₹6,25,000.00
  Profit/Loss: ₹1,25,000.00
  Overall Return: 25.00%

============================================================
Generating Portfolio Time Series...
============================================================

Last 10 Days:
       date  total_value  day_change  day_change_pct  cumulative_return_pct
 2024-11-11   623450.50    1250.25            0.20                  24.69
 2024-11-12   625120.75    1670.25            0.27                  25.02
 2024-11-13   623890.00   -1230.75           -0.20                  24.78
 ...

============================================================
Monthly Returns:
============================================================
    month  start_value   end_value  monthly_return_pct
  2024-01    500000.00  515000.00                3.00
  2024-02    515000.00  535000.00                3.88
  2024-03    535000.00  548000.00                2.43
  ...
```

## Time Series Data Columns

### Daily Time Series (`portfolio_timeseries_*.csv`)

| Column | Description |
|--------|-------------|
| `date` | Trading date |
| `total_value` | Portfolio value (₹) |
| `day_change` | Absolute change from previous day (₹) |
| `day_change_pct` | Percentage change from previous day (%) |
| `cumulative_return_pct` | Return from start date (%) |
| `holdings_count` | Number of holdings valued |

### Monthly Returns (`portfolio_monthly_*.csv`)

| Column | Description |
|--------|-------------|
| `month` | Month (YYYY-MM) |
| `start_value` | Portfolio value at month start (₹) |
| `end_value` | Portfolio value at month end (₹) |
| `monthly_return_pct` | Monthly return (%) |
| `best_day` | Date with highest gain |
| `worst_day` | Date with lowest gain/highest loss |
| `trading_days` | Number of trading days in month |

## Python API

### Calculate Time Series

```python
from portfolio_calculator import PortfolioCalculator

calc = PortfolioCalculator()

# Get full history
timeseries_df = calc.calculate_portfolio_timeseries('CLIENT123')

# Get date range
timeseries_df = calc.calculate_portfolio_timeseries(
    'CLIENT123',
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# Access data
print(f"Latest value: ₹{timeseries_df['total_value'].iloc[-1]:,.2f}")
print(f"Best day: {timeseries_df.loc[timeseries_df['day_change'].idxmax(), 'date']}")
print(f"Cumulative return: {timeseries_df['cumulative_return_pct'].iloc[-1]:.2f}%")
```

### Calculate Monthly Returns

```python
monthly_df = calc.calculate_monthly_returns('CLIENT123')

# Last 12 months
recent_months = monthly_df.tail(12)
print(recent_months[['month', 'monthly_return_pct']])

# Best performing month
best_month = monthly_df.loc[monthly_df['monthly_return_pct'].idxmax()]
print(f"Best month: {best_month['month']} ({best_month['monthly_return_pct']:.2f}%)")
```

## How It Works

### Time Series Calculation Logic

```python
For each trading day:
  1. Get NAV for each holding on that date
  2. Calculate: portfolio_value = Σ(quantity × NAV)
  3. If NAV missing, use last known NAV (forward fill)
  4. Calculate daily change and cumulative return
```

**SQL Query:**
```sql
-- Get holdings
SELECT isin, quantity FROM holdings
WHERE client_code = 'CLIENT123' AND quantity > 0

-- Get NAV history for all holdings
SELECT isin, date, nav FROM mf_nav_history
WHERE isin IN ('INF123...', 'INF456...')
ORDER BY date, isin

-- Portfolio value on 2024-11-20:
-- = (100 units × ₹50.25) + (200 units × ₹125.50) + ...
```

## Use Cases

### 1. Performance Charts

```python
import matplotlib.pyplot as plt

calc = PortfolioCalculator()
ts = calc.calculate_portfolio_timeseries('CLIENT123')

plt.figure(figsize=(12, 6))
plt.plot(ts['date'], ts['total_value'])
plt.title('Portfolio Value Over Time')
plt.xlabel('Date')
plt.ylabel('Value (₹)')
plt.grid(True)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('portfolio_chart.png')
```

### 2. Email Reports

```python
from datetime import datetime, timedelta

# Last 30 days performance
end_date = datetime.now().date()
start_date = end_date - timedelta(days=30)

ts = calc.calculate_portfolio_timeseries(
    'CLIENT123',
    start_date=start_date.isoformat(),
    end_date=end_date.isoformat()
)

# Generate HTML report
html = f"""
<h2>30-Day Portfolio Performance</h2>
<p>Start Value: ₹{ts['total_value'].iloc[0]:,.2f}</p>
<p>End Value: ₹{ts['total_value'].iloc[-1]:,.2f}</p>
<p>Change: {ts['cumulative_return_pct'].iloc[-1]:.2f}%</p>
"""
```

### 3. Dashboard API

```python
from flask import Flask, jsonify
from portfolio_calculator import PortfolioCalculator

app = Flask(__name__)

@app.route('/api/portfolio/<client_code>/timeseries')
def get_timeseries(client_code):
    calc = PortfolioCalculator()
    ts = calc.calculate_portfolio_timeseries(client_code)
    
    return jsonify({
        'dates': ts['date'].astype(str).tolist(),
        'values': ts['total_value'].tolist(),
        'returns': ts['cumulative_return_pct'].tolist()
    })

@app.route('/api/portfolio/<client_code>/monthly')
def get_monthly(client_code):
    calc = PortfolioCalculator()
    monthly = calc.calculate_monthly_returns(client_code)
    
    return jsonify(monthly.to_dict(orient='records'))
```

## Automated Reports

### Add to Daily Pipeline

Update `daily_sync.sh`:

```bash
# After NAV sync
log "Generating portfolio time series..."
python3 -c "
from portfolio_calculator import PortfolioCalculator
calc = PortfolioCalculator()

# Get all clients
clients = ['CLIENT001', 'CLIENT002', 'CLIENT003']

for client in clients:
    ts = calc.calculate_portfolio_timeseries(client)
    ts.to_csv(f'reports/timeseries_{client}.csv', index=False)
    
    monthly = calc.calculate_monthly_returns(client)
    monthly.to_csv(f'reports/monthly_{client}.csv', index=False)
" >> "$LOG_FILE" 2>&1
```

## Performance Optimization

### For Large Portfolios

```python
# Use date range to limit data
timeseries_df = calc.calculate_portfolio_timeseries(
    'CLIENT123',
    start_date='2024-01-01'  # Only last year
)

# Or last N months
from datetime import datetime, timedelta
start = (datetime.now() - timedelta(days=180)).date()
timeseries_df = calc.calculate_portfolio_timeseries(
    'CLIENT123',
    start_date=start.isoformat()
)
```

### Database Indexes

Ensure these indexes exist for fast queries:

```sql
CREATE INDEX idx_nav_history_isin_date ON mf_nav_history(isin, date DESC);
CREATE INDEX idx_holdings_client ON holdings(client_code);
```

## Troubleshooting

**Time series has gaps:**
- Weekends/holidays won't have data (NAV only on trading days)
- Use forward fill (already implemented) for missing dates

**Performance slow:**
- Add date range filters
- Ensure database indexes
- Use monthly views for long periods

**NAV missing for some ISINs:**
- Run `./historical_setup.sh` to download missing NAV data
- Check `mf_nav_history` for that ISIN

## Example Output

### Time Series Sample
```csv
date,total_value,day_change,day_change_pct,cumulative_return_pct,holdings_count
2024-11-01,500000.00,0.00,0.00,0.00,5
2024-11-04,502500.50,2500.50,0.50,0.50,5
2024-11-05,505125.75,2625.25,0.52,1.03,5
2024-11-06,503890.25,-1235.50,-0.24,0.78,5
```

### Monthly Returns Sample
```csv
month,start_value,end_value,monthly_return_pct,best_day,worst_day,trading_days
2024-01,500000.00,515000.00,3.00,2024-01-15,2024-01-22,21
2024-02,515000.00,535000.00,3.88,2024-02-08,2024-02-14,20
2024-03,535000.00,548000.00,2.43,2024-03-12,2024-03-25,21
```

## Visualization Ideas

1. **Line Chart**: Portfolio value over time
2. **Area Chart**: Cumulative returns
3. **Bar Chart**: Monthly returns
4. **Heatmap**: Daily changes by month
5. **Candlestick**: Daily high/low/open/close (if intraday data available)
