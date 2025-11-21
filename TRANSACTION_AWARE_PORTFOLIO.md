# Transaction-Aware Portfolio Computation Guide

## The Problem

Current implementation calculates historical portfolio using **current holdings**, which is incorrect because:

❌ If you bought 100 units on Nov 15, it shows you had them on Nov 1 too  
❌ If you sold 50 units on Nov 10, it still shows all 100 units before that  
❌ Ignores when units were actually purchased/redeemed  

## The Solution

Use **transaction history** to reconstruct holdings on each date.

## Assumptions About Your Transaction Table

You likely have a transactions table like:

```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    client_code VARCHAR(20) NOT NULL,
    isin VARCHAR(12) NOT NULL,
    folio_no VARCHAR(20),
    transaction_date DATE NOT NULL,
    transaction_type VARCHAR(10) NOT NULL, -- 'BUY' or 'SELL'
    units NUMERIC(15, 4) NOT NULL,
    nav NUMERIC(10, 4) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## How Transaction-Aware Calculation Works

### Step-by-Step Process

```
Date: 2024-11-01
Holdings: {} (empty)
Portfolio Value: ₹0

Transaction: BUY 100 units of ISIN1 @ ₹50
Date: 2024-11-05
Holdings: {ISIN1: 100 units}
Portfolio Value: 100 × ₹51 (NAV on Nov 5) = ₹5,100

Transaction: BUY 50 units of ISIN2 @ ₹120
Date: 2024-11-10
Holdings: {ISIN1: 100 units, ISIN2: 50 units}
Portfolio Value: (100 × ₹52) + (50 × ₹122) = ₹11,300

Transaction: SELL 30 units of ISIN1 @ ₹53
Date: 2024-11-15
Holdings: {ISIN1: 70 units, ISIN2: 50 units}
Portfolio Value: (70 × ₹54) + (50 × ₹125) = ₹10,030
```

## Implementation

### Updated `portfolio_timeseries_db.py`

Key changes needed:

```python
def get_holdings_on_date(self, client_code, date):
    """
    Reconstruct holdings as of a specific date using transaction history.
    
    Returns:
        DataFrame with columns: isin, quantity, avg_nav
    """
    query = """
        WITH transaction_summary AS (
            SELECT 
                isin,
                folio_no,
                SUM(CASE 
                    WHEN transaction_type = 'BUY' THEN units
                    WHEN transaction_type = 'SELL' THEN -units
                    ELSE 0
                END) as quantity,
                SUM(CASE 
                    WHEN transaction_type = 'BUY' THEN units * nav
                    WHEN transaction_type = 'SELL' THEN -units * nav
                    ELSE 0
                END) / NULLIF(SUM(CASE 
                    WHEN transaction_type = 'BUY' THEN units
                    WHEN transaction_type = 'SELL' THEN -units
                    ELSE 0
                END), 0) as avg_nav
            FROM transactions
            WHERE client_code = :client_code
            AND transaction_date <= :date
            GROUP BY isin, folio_no
            HAVING SUM(CASE 
                WHEN transaction_type = 'BUY' THEN units
                WHEN transaction_type = 'SELL' THEN -units
                ELSE 0
            END) > 0
        )
        SELECT 
            isin,
            SUM(quantity) as quantity,
            AVG(avg_nav) as avg_nav
        FROM transaction_summary
        GROUP BY isin
    """
    
    return pd.read_sql(
        text(query),
        db.session.bind,
        params={'client_code': client_code, 'date': date}
    )
```

### Updated Time Series Calculation

```python
def update_client_timeseries_with_transactions(self, client_code, date=None):
    """
    Calculate portfolio value using transaction history.
    """
    # Get holdings as of this date (not current holdings!)
    holdings_df = self.get_holdings_on_date(client_code, date)
    
    if holdings_df.empty:
        # No holdings on this date
        return None
    
    # Rest of calculation remains same...
    # Get NAV for each holding
    # Calculate total value
    # Store in database
```

## Verification Query

Check if holdings calculation is correct:

```sql
-- Get holdings on Nov 15, 2024
SELECT 
    isin,
    SUM(CASE 
        WHEN transaction_type = 'BUY' THEN units
        WHEN transaction_type = 'SELL' THEN -units
    END) as current_quantity
FROM transactions
WHERE client_code = 'CLIENT123'
AND transaction_date <= '2024-11-15'
GROUP BY isin
HAVING SUM(CASE 
    WHEN transaction_type = 'BUY' THEN units
    WHEN transaction_type = 'SELL' THEN -units
END) > 0;
```

## Important Considerations

### 1. **Transaction Date vs Settlement Date**

If transactions have a settlement lag:

```sql
-- Use settlement_date instead of transaction_date
WHERE settlement_date <= :date
```

### 2. **Average NAV Calculation**

For FIFO (First In, First Out):

```sql
-- More complex, need to track lots
-- Better to store in holdings table and update via triggers
```

For Weighted Average (simpler):

```sql
avg_nav = SUM(buy_amount) / SUM(buy_units)
```

### 3. **Corporate Actions**

Handle splits, bonuses, dividends:

```sql
-- Dividend reinvestment = BUY transaction
-- Bonus units = BUY at ₹0
-- Split = Adjust all units proportionally
```

## Recommended Approach

### Option 1: Transaction-Based (Real-time)

✅ **Pros**: Always accurate, handles history correctly  
❌ **Cons**: Slower for large transaction history  

```python
# Calculate on-the-fly from transactions
holdings = get_holdings_on_date(client_code, date)
```

### Option 2: Snapshot-Based (Fast)

✅ **Pros**: Very fast queries  
❌ **Cons**: Need to maintain snapshots  

```python
# Store daily holdings snapshot
UPDATE holdings 
SET quantity = (calculated from transactions)
WHERE date = today
```

### Option 3: Hybrid (Recommended)

✅ **Pros**: Fast AND accurate  
❌ **Cons**: Slightly more complex  

```python
# Use current holdings table for recent dates
# Use transaction history for backfilling old dates
if date >= (today - 30 days):
    use holdings table
else:
    calculate from transactions
```

## Migration Plan

### 1. Update Holdings Table

Add transaction tracking:

```sql
ALTER TABLE holdings
ADD COLUMN last_transaction_date DATE,
ADD COLUMN inception_date DATE;  -- First transaction date
```

### 2. Create View for Current Holdings

```sql
CREATE VIEW current_holdings AS
SELECT 
    client_code,
    isin,
    folio_no,
    SUM(CASE 
        WHEN transaction_type = 'BUY' THEN units
        WHEN transaction_type = 'SELL' THEN -units
    END) as quantity,
    -- Weighted average NAV
    SUM(CASE WHEN transaction_type = 'BUY' THEN units * nav END) /
    NULLIF(SUM(CASE WHEN transaction_type = 'BUY' THEN units END), 0) as avg_nav,
    MIN(transaction_date) as inception_date,
    MAX(transaction_date) as last_transaction_date
FROM transactions
GROUP BY client_code, isin, folio_no
HAVING SUM(CASE 
    WHEN transaction_type = 'BUY' THEN units
    WHEN transaction_type = 'SELL' THEN -units
END) > 0;
```

### 3. Maintain Holdings via Triggers

```sql
CREATE OR REPLACE FUNCTION update_holdings_on_transaction()
RETURNS TRIGGER AS $$
BEGIN
    -- Recalculate holdings for this client+isin
    INSERT INTO holdings (client_code, isin, folio_no, quantity, avg_nav)
    SELECT 
        client_code, isin, folio_no,
        SUM(CASE WHEN transaction_type = 'BUY' THEN units ELSE -units END),
        SUM(CASE WHEN transaction_type = 'BUY' THEN units * nav END) / 
        SUM(CASE WHEN transaction_type = 'BUY' THEN units END)
    FROM transactions
    WHERE client_code = NEW.client_code AND isin = NEW.isin
    GROUP BY client_code, isin, folio_no
    ON CONFLICT (client_code, isin, folio_no) 
    DO UPDATE SET
        quantity = EXCLUDED.quantity,
        avg_nav = EXCLUDED.avg_nav,
        last_updated = NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER transaction_updates_holdings
AFTER INSERT OR UPDATE OR DELETE ON transactions
FOR EACH ROW
EXECUTE FUNCTION update_holdings_on_transaction();
```

## Testing Transaction Accuracy

```python
from datetime import datetime, timedelta

# Test case: Known transaction history
transactions = [
    {'date': '2024-01-01', 'type': 'BUY', 'units': 100, 'nav': 50},
    {'date': '2024-06-01', 'type': 'BUY', 'units': 50, 'nav': 55},
    {'date': '2024-09-01', 'type': 'SELL', 'units': 30, 'nav': 60},
]

# Expected holdings on different dates
assert get_holdings_on_date('CLIENT123', '2023-12-31') == {}
assert get_holdings_on_date('CLIENT123', '2024-01-01')['quantity'] == 100
assert get_holdings_on_date('CLIENT123', '2024-06-01')['quantity'] == 150
assert get_holdings_on_date('CLIENT123', '2024-09-01')['quantity'] == 120
```

## Summary

✅ **Use transactions table** as source of truth  
✅ **Reconstruct holdings** for each historical date  
✅ **Update holdings table** via triggers for current values  
✅ **Verify** transaction sums match current holdings  
✅ **Handle** corporate actions, splits, dividends  

**Next Step**: I'll create the updated `portfolio_timeseries_db.py` with transaction support.
