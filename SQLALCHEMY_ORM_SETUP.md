# SQLAlchemy ORM Setup for Portfolio Models

## Quick Start

### 1. Add Models to Your Database

You have two options:

#### Option A: Add to existing `SQL/data/models.py`

Open `SQL/data/models.py` and add:

```python
from portfolio_models import (
    PortfolioTimeSeries, 
    PortfolioHoldingsSnapshot, 
    Transaction
)
```

#### Option B: Import in `SQL/setup_db.py`

Add to your imports:

```python
from portfolio_models import PortfolioTimeSeries, PortfolioHoldingsSnapshot, Transaction
```

### 2. Create Tables

```bash
python3 -c "
from SQL.setup_db import create_app, db
from portfolio_models import PortfolioTimeSeries, PortfolioHoldingsSnapshot, Transaction

app = create_app()
with app.app_context():
    db.create_all()
    print('✓ Tables created successfully')
"
```

### 3. Verify Tables

```bash
python3 -c "
from SQL.setup_db import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    for table in ['portfolio_timeseries', 'portfolio_holdings_snapshot', 'transactions']:
        if table in tables:
            print(f'✓ {table}')
        else:
            print(f'✗ {table} - MISSING')
"
```

## What Changed

### Before (Raw SQL)
```python
from sqlalchemy import text

query = text("""
    INSERT INTO portfolio_timeseries (...)
    VALUES (:client_code, :date, ...)
    ON CONFLICT (client_code, date)
    DO UPDATE SET ...
""")

db.session.execute(query, params)
```

### After (SQLAlchemy ORM)
```python
from sqlalchemy.dialects.postgresql import insert
from portfolio_models import PortfolioTimeSeries

stmt = insert(PortfolioTimeSeries).values(
    client_code=client_code,
    date=date,
    portfolio_value=value
)

stmt = stmt.on_conflict_do_update(
    index_elements=['client_code', 'date'],
    set_=dict(portfolio_value=stmt.excluded.portfolio_value)
)

db.session.execute(stmt)
```

## Model Definitions

### PortfolioTimeSeries
- Stores daily portfolio values
- Unique constraint on (client_code, date)
- Indexed for fast queries

### PortfolioHoldingsSnapshot
- Stores daily holdings detail
- Unique constraint on (client_code, date, isin)
- Foreign keys to bse_details and mf_fund

### Transaction
- Stores buy/sell transactions
- Indexed on (client_code, transaction_date)
- Supports transaction types: BUY, SELL, PURCHASE, REDEMPTION

## Usage

### Query Examples

```python
from portfolio_models import PortfolioTimeSeries
from datetime import datetime, timedelta

# Get last 30 days for a client
recent = (
    db.session.query(PortfolioTimeSeries)
    .filter(
        PortfolioTimeSeries.client_code == 'CLIENT123',
        PortfolioTimeSeries.date >= datetime.now().date() - timedelta(days=30)
    )
    .order_by(PortfolioTimeSeries.date.desc())
    .all()
)

for record in recent:
    print(f"{record.date}: ₹{record.portfolio_value:,.2f}")
```

### Insert/Update

```python
from sqlalchemy.dialects.postgresql import insert

# Upsert (insert or update if exists)
stmt = insert(PortfolioTimeSeries).values(
    client_code='CLIENT123',
    date='2024-11-20',
    portfolio_value=125000.50
)

stmt = stmt.on_conflict_do_update(
    index_elements=['client_code', 'date'],
    set_=dict(portfolio_value=stmt.excluded.portfolio_value)
)

db.session.execute(stmt)
db.session.commit()
```

## Benefits of ORM

✅ **Type Safety** - Python objects instead of string queries  
✅ **Auto-completion** - IDE support for columns/methods  
✅ **Less SQL Injection Risk** - Parameters handled safely  
✅ **Easier Testing** - Mock models instead of database  
✅ **Better Refactoring** - Change model, updates everywhere  

## Migration from Raw SQL

All `text()` queries have been replaced with ORM equivalents:

- ✅ `get_holdings_on_date()` - Uses Transaction model with case/func
- ✅ `update_timeseries_for_date()` - Uses insert().on_conflict_do_update()
- ✅ `backfill_client_timeseries()` - Uses NavHistory and Transaction models
- ✅ `verify_holdings_consistency()` - Uses ORM subqueries

**No functionality changed - just the implementation!**
