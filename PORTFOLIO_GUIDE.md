# Portfolio Valuation Guide

## Overview

The `portfolio_calculator.py` module calculates current portfolio values and returns for client holdings by combining:
- Holdings data from `holdings` table
- Latest NAV data from `mf_nav_history` table

## Features

✅ Calculate current portfolio value for each holding  
✅ Calculate profit/loss (absolute and percentage)  
✅ Generate client-wise portfolio summaries  
✅ Export portfolio reports to CSV  
✅ Supports individual client or all clients  

## Usage

### 1. Calculate Portfolio for Specific Client

```bash
python3 portfolio_calculator.py CLIENT123
```

**Output:**
```
Portfolio Summary for CLIENT123:
  Total Holdings: 5
  Total Invested: ₹5,00,000.00
  Current Value: ₹6,25,000.00
  Profit/Loss: ₹1,25,000.00
  Overall Return: 25.00%

Exported to: portfolio_CLIENT123.csv
```

### 2. Calculate Portfolio for All Clients

```bash
python3 portfolio_calculator.py
```

Generates: `portfolio_all_clients.csv`

### 3. Use in Custom Scripts

```python
from portfolio_calculator import PortfolioCalculator

calc = PortfolioCalculator()

# Get portfolio DataFrame
portfolio_df = calc.calculate_portfolio_values('CLIENT123')

# Get summary
summary = calc.get_client_summary('CLIENT123')
print(f"Total Return: {summary['overall_return_pct']:.2f}%")

# Export report
calc.export_portfolio_report('my_report.csv', 'CLIENT123')
```

## Portfolio Report Columns

| Column | Description |
|--------|-------------|
| `client_code` | Client identifier |
| `isin` | Fund ISIN |
| `scheme_name` | Mutual fund name |
| `folio_no` | Folio number |
| `quantity` | Units held |
| `avg_nav` | Average purchase NAV |
| `current_nav` | Latest NAV |
| `invested_value` | Total invested (quantity × avg_nav) |
| `current_value` | Current value (quantity × current_nav) |
| `profit_loss` | Absolute P&L (₹) |
| `return_pct` | Return percentage (%) |
| `nav_date` | NAV as of date |

## Integration with Daily Pipeline

### Option 1: Generate Reports After Daily Sync

Update `daily_sync.sh`:

```bash
#!/bin/bash
# ... existing sync code ...

# Step 3: Generate portfolio reports
log "Step 3: Generating portfolio reports..."
python3 portfolio_calculator.py >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    handle_error "Portfolio calculation failed"
fi
log "Portfolio reports generated"
```

### Option 2: Add to main.py

```python
# main.py
from portfolio_calculator import PortfolioCalculator

def main(master_list_path='navdata/isin_master_list.csv'):
    # ... existing NAV download and returns calculation ...
    
    # Calculate portfolio values
    print("Calculating portfolio values...")
    calc = PortfolioCalculator()
    calc.export_portfolio_report('navdata/portfolio_report.csv')
    print("Portfolio report generated")

if __name__ == "__main__":
    main()
```

## Database Schema Requirements

### Current Holdings Table

Your existing `holdings` table already has required fields:
- ✅ `client_code`
- ✅ `isin`
- ✅ `quantity`
- ✅ `avg_nav`
- ✅ `folio_no`

### Optional: Add Computed Columns

If you want to store calculated values in the `holdings` table:

```sql
ALTER TABLE holdings 
ADD COLUMN current_nav NUMERIC(10, 4),
ADD COLUMN current_value NUMERIC(15, 2),
ADD COLUMN profit_loss NUMERIC(15, 2),
ADD COLUMN return_pct NUMERIC(10, 2),
ADD COLUMN nav_as_of_date DATE;
```

Then use `update_holding_current_values()` function to populate these.

## SQL Queries Used

### Get Latest NAV for Each ISIN

```sql
SELECT DISTINCT ON (isin) 
    isin, 
    nav, 
    date as nav_date
FROM mf_nav_history
ORDER BY isin, date DESC;
```

### Get Holdings with Scheme Names

```sql
SELECT 
    h.client_code,
    h.isin,
    s.scheme_name,
    h.quantity,
    h.avg_nav
FROM holdings h
LEFT JOIN mf_fund s ON h.isin = s.isin
WHERE h.quantity > 0
ORDER BY h.client_code, h.isin;
```

## Example Workflow

### Daily Portfolio Valuation

```bash
# 1. Run daily sync (updates NAV data)
./daily_sync.sh

# 2. Generate portfolio reports
python3 portfolio_calculator.py

# 3. Reports available at:
#    - portfolio_all_clients.csv
```

### Client-Specific Reports

```bash
# Generate for specific client
python3 portfolio_calculator.py CLIENT001

# Email or upload to client portal
```

### API Integration

Create REST endpoint:

```python
from flask import Flask, jsonify
from portfolio_calculator import PortfolioCalculator

app = Flask(__name__)

@app.route('/api/portfolio/<client_code>')
def get_portfolio(client_code):
    calc = PortfolioCalculator()
    summary = calc.get_client_summary(client_code)
    return jsonify(summary)

@app.route('/api/portfolio/<client_code>/detailed')
def get_portfolio_detailed(client_code):
    calc = PortfolioCalculator()
    portfolio_df = calc.calculate_portfolio_values(client_code)
    return jsonify(portfolio_df.to_dict(orient='records'))
```

## Performance Considerations

- **Latest NAV Query**: Uses `DISTINCT ON` for optimal performance
- **Batch Processing**: Processes all holdings in single query
- **Indexing**: Ensure indexes on:
  - `holdings.client_code`
  - `holdings.isin`
  - `mf_nav_history(isin, date DESC)`

## Error Handling

The calculator handles:
- ✅ Missing NAV data (logs warning, skips holding)
- ✅ Zero/NULL avg_nav (calculates current value only)
- ✅ Empty holdings (returns empty DataFrame)
- ✅ Database connection errors (SQLAlchemy exceptions)

## Customization

### Add Custom Metrics

```python
# Extend PortfolioCalculator class
class CustomPortfolioCalculator(PortfolioCalculator):
    
    def calculate_xirr(self, client_code):
        """Calculate XIRR for client portfolio"""
        # Your XIRR logic here
        pass
    
    def get_top_performers(self, client_code, limit=5):
        """Get top N performing holdings"""
        portfolio_df = self.calculate_portfolio_values(client_code)
        return portfolio_df.nlargest(limit, 'return_pct')
```

## Troubleshooting

**No NAV found for ISIN:**
- Ensure NAV data is synced for that ISIN
- Check `mf_nav_history` table
- Run `./historical_setup.sh` to download missing data

**Returns showing as NULL:**
- Check if `avg_nav` is populated in holdings
- Ensure holdings have valid purchase NAV

**Performance slow:**
- Add database indexes
- Use `client_code` filter for specific clients
- Consider caching latest NAVs

## Next Steps

1. **Automated Reports**: Schedule portfolio reports via cron
2. **Email Integration**: Send reports to clients automatically
3. **Dashboard**: Build web dashboard showing portfolio performance
4. **Alerts**: Notify clients of significant gains/losses
