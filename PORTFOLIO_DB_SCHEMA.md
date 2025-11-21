# Portfolio Time Series Database Storage

## Overview

For advanced analytics, portfolio time series should be stored in the database rather than calculated on-the-fly.

## Database Schema

### New Table: `portfolio_timeseries`

```sql
CREATE TABLE portfolio_timeseries (
    id SERIAL PRIMARY KEY,
    client_code VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    portfolio_value NUMERIC(15, 2) NOT NULL,
    invested_value NUMERIC(15, 2),
    day_change NUMERIC(15, 2),
    day_change_pct NUMERIC(10, 4),
    cumulative_return_pct NUMERIC(10, 4),
    holdings_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(client_code, date),
    FOREIGN KEY (client_code) REFERENCES bse_details(bse_client_code)
);

CREATE INDEX idx_portfolio_ts_client_date ON portfolio_timeseries(client_code, date DESC);
CREATE INDEX idx_portfolio_ts_date ON portfolio_timeseries(date DESC);
```

### New Table: `portfolio_holdings_snapshot`

Store daily snapshot of what each client held:

```sql
CREATE TABLE portfolio_holdings_snapshot (
    id SERIAL PRIMARY KEY,
    client_code VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    isin VARCHAR(12) NOT NULL,
    quantity NUMERIC(15, 4) NOT NULL,
    nav NUMERIC(10, 4) NOT NULL,
    value NUMERIC(15, 2) NOT NULL,
    
    UNIQUE(client_code, date, isin),
    FOREIGN KEY (client_code) REFERENCES bse_details(bse_client_code),
    FOREIGN KEY (isin) REFERENCES mf_fund(isin)
);

CREATE INDEX idx_holdings_snapshot_client_date ON portfolio_holdings_snapshot(client_code, date DESC);
```

## SQLAlchemy Models

Add to your `models.py`:

```python
class PortfolioTimeSeries(db.Model):
    """Daily portfolio value time series for analytics"""
    __tablename__ = "portfolio_timeseries"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_code = db.Column(db.String(20), db.ForeignKey("bse_details.bse_client_code"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    portfolio_value = db.Column(db.Numeric(15, 2), nullable=False)
    invested_value = db.Column(db.Numeric(15, 2))
    day_change = db.Column(db.Numeric(15, 2))
    day_change_pct = db.Column(db.Numeric(10, 4))
    cumulative_return_pct = db.Column(db.Numeric(10, 4))
    holdings_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('client_code', 'date', name='uq_portfolio_ts_client_date'),
    )


class PortfolioHoldingsSnapshot(db.Model):
    """Daily snapshot of holdings for each client"""
    __tablename__ = "portfolio_holdings_snapshot"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_code = db.Column(db.String(20), db.ForeignKey("bse_details.bse_client_code"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    isin = db.Column(db.String(12), db.ForeignKey("mf_fund.isin"), nullable=False)
    quantity = db.Column(db.Numeric(15, 4), nullable=False)
    nav = db.Column(db.Numeric(10, 4), nullable=False)
    value = db.Column(db.Numeric(15, 2), nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('client_code', 'date', 'isin', name='uq_holdings_snapshot'),
    )
```

## Benefits of Storing Time Series

### 1. **Performance**
- ✅ Fast queries (no on-the-fly calculation)
- ✅ Pre-aggregated data
- ✅ Indexed for quick retrieval

### 2. **Analytics**
- ✅ Complex queries (rolling averages, volatility)
- ✅ Cross-client analysis
- ✅ Historical comparisons
- ✅ Trend analysis

### 3. **Consistency**
- ✅ Same historical values always
- ✅ Audit trail
- ✅ Point-in-time accuracy

## Usage Examples

### Query Last 30 Days

```sql
SELECT 
    date,
    portfolio_value,
    day_change,
    cumulative_return_pct
FROM portfolio_timeseries
WHERE client_code = 'CLIENT123'
AND date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY date DESC;
```

### Monthly Aggregates

```sql
SELECT 
    DATE_TRUNC('month', date) as month,
    MIN(portfolio_value) as month_low,
    MAX(portfolio_value) as month_high,
    AVG(portfolio_value) as month_avg,
    SUM(day_change) as month_total_change
FROM portfolio_timeseries
WHERE client_code = 'CLIENT123'
GROUP BY DATE_TRUNC('month', date)
ORDER BY month DESC;
```

### Volatility Analysis

```sql
SELECT 
    client_code,
    STDDEV(day_change_pct) as volatility,
    AVG(day_change_pct) as avg_daily_return,
    MAX(day_change_pct) as best_day,
    MIN(day_change_pct) as worst_day
FROM portfolio_timeseries
WHERE date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY client_code
ORDER BY volatility DESC;
```

### Compare Clients

```sql
SELECT 
    client_code,
    MAX(portfolio_value) as current_value,
    MAX(cumulative_return_pct) as total_return,
    AVG(portfolio_value) as avg_value
FROM portfolio_timeseries
WHERE date >= CURRENT_DATE - INTERVAL '365 days'
GROUP BY client_code
ORDER BY total_return DESC;
```

### Rolling 30-Day Average

```sql
SELECT 
    date,
    portfolio_value,
    AVG(portfolio_value) OVER (
        ORDER BY date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) as rolling_30d_avg
FROM portfolio_timeseries
WHERE client_code = 'CLIENT123'
ORDER BY date DESC
LIMIT 90;
```

## Python API

### Store Time Series

See `portfolio_timeseries_db.py` for implementation.

```python
from portfolio_timeseries_db import PortfolioTimeSeriesDB

db_manager = PortfolioTimeSeriesDB()

# Calculate and store for one client
db_manager.update_client_timeseries('CLIENT123')

# Calculate and store for all clients
db_manager.update_all_clients_timeseries()

# Backfill historical data
db_manager.backfill_timeseries('CLIENT123', days_back=365)
```

### Query Time Series

```python
# Get last 30 days
df = db_manager.get_timeseries('CLIENT123', days=30)

# Get date range
df = db_manager.get_timeseries(
    'CLIENT123',
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# Get all clients for a date
df = db_manager.get_all_clients_on_date('2024-11-20')
```

## Daily Update Process

```bash
# In daily_sync.sh, add:
python3 portfolio_timeseries_db.py --update-all
```

This will:
1. Get all clients with holdings
2. Calculate today's portfolio value
3. Store in `portfolio_timeseries` table
4. Store holdings snapshot in `portfolio_holdings_snapshot`

## Migration Path

### 1. Create Tables

```bash
# Run migration
python3 -c "
from SQL.setup_db import create_app, db
from portfolio_models import PortfolioTimeSeries, PortfolioHoldingsSnapshot

app = create_app()
with app.app_context():
    db.create_all()
    print('Tables created successfully')
"
```

### 2. Backfill Historical Data

```bash
# Backfill last year
python3 portfolio_timeseries_db.py --backfill-all --days 365
```

### 3. Enable Daily Updates

```bash
# Add to crontab (runs after daily_sync.sh)
5 18 * * * cd /path/to/navtimeseries && python3 portfolio_timeseries_db.py --update-all
```

## Advanced Analytics Examples

### Sharpe Ratio

```python
df = db_manager.get_timeseries('CLIENT123', days=365)
returns = df['day_change_pct'].values
sharpe = (returns.mean() / returns.std()) * np.sqrt(252)
```

### Maximum Drawdown

```python
df = db_manager.get_timeseries('CLIENT123', days=365)
peak = df['portfolio_value'].expanding(min_periods=1).max()
drawdown = (df['portfolio_value'] - peak) / peak
max_drawdown = drawdown.min()
```

### Portfolio Comparison Chart

```python
import matplotlib.pyplot as plt

clients = ['CLIENT001', 'CLIENT002', 'CLIENT003']
for client in clients:
    df = db_manager.get_timeseries(client, days=90)
    plt.plot(df['date'], df['cumulative_return_pct'], label=client)

plt.legend()
plt.title('90-Day Performance Comparison')
plt.show()
```

## Performance Considerations

### Indexes

```sql
-- Already included in schema
CREATE INDEX idx_portfolio_ts_client_date ON portfolio_timeseries(client_code, date DESC);
CREATE INDEX idx_portfolio_ts_date ON portfolio_timeseries(date DESC);
```

### Partitioning (for large datasets)

```sql
-- Partition by year
CREATE TABLE portfolio_timeseries_2024 PARTITION OF portfolio_timeseries
FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

### Archival

```sql
-- Archive old data (> 5 years)
DELETE FROM portfolio_timeseries
WHERE date < CURRENT_DATE - INTERVAL '5 years';
```

## Summary

✅ **Structured Storage**: Time series stored in database  
✅ **Fast Queries**: Indexed for performance  
✅ **Analytics Ready**: Complex queries possible  
✅ **Historical Accuracy**: Point-in-time snapshots  
✅ **Daily Updates**: Automated via cron  

**Next**: Implement `portfolio_timeseries_db.py` module for database operations.
