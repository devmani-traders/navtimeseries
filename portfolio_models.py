"""
SQLAlchemy Models for Portfolio Time Series

Add these models to your existing SQL/models.py file.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, UniqueConstraint, Index
from SQL.setup_db import db


class PortfolioTimeSeries(db.Model):
    """Daily portfolio value time series for analytics"""
    __tablename__ = "portfolio_timeseries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_code = Column(String(20), ForeignKey("bse_details.bse_client_code"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    portfolio_value = Column(Numeric(15, 2), nullable=False)
    invested_value = Column(Numeric(15, 2))
    day_change = Column(Numeric(15, 2))
    day_change_pct = Column(Numeric(10, 4))
    cumulative_return_pct = Column(Numeric(10, 4))
    holdings_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('client_code', 'date', name='uq_portfolio_ts_client_date'),
        Index('idx_portfolio_ts_client_date', 'client_code', 'date'),
    )
    
    def __repr__(self):
        return f"<PortfolioTimeSeries(client={self.client_code}, date={self.date}, value={self.portfolio_value})>"


class PortfolioHoldingsSnapshot(db.Model):
    """Daily snapshot of holdings for each client"""
    __tablename__ = "portfolio_holdings_snapshot"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_code = Column(String(20), ForeignKey("bse_details.bse_client_code"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    isin = Column(String(12), ForeignKey("mf_fund.isin"), nullable=False)
    quantity = Column(Numeric(15, 4), nullable=False)
    nav = Column(Numeric(10, 4), nullable=False)
    value = Column(Numeric(15, 2), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('client_code', 'date', 'isin', name='uq_holdings_snapshot'),
        Index('idx_holdings_snapshot_client_date', 'client_code', 'date'),
    )
    
    def __repr__(self):
        return f"<PortfolioHoldingsSnapshot(client={self.client_code}, date={self.date}, isin={self.isin})>"


class Transaction(db.Model):
    """Fund transaction history"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_code = Column(String(20), ForeignKey("bse_details.bse_client_code"), nullable=False, index=True)
    isin = Column(String(12), ForeignKey("mf_fund.isin"), nullable=False, index=True)
    folio_no = Column(String(20))
    transaction_date = Column(Date, nullable=False, index=True)
    transaction_type = Column(String(20), nullable=False)  # BUY, SELL, PURCHASE, REDEMPTION
    units = Column(Numeric(15, 4), nullable=False)
    nav = Column(Numeric(10, 4), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    remarks = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_transactions_client_date', 'client_code', 'transaction_date'),
        Index('idx_transactions_isin_date', 'isin', 'transaction_date'),
    )
    
    def __repr__(self):
        return f"<Transaction(client={self.client_code}, type={self.transaction_type}, units={self.units})>"


# Migration SQL (if you prefer to run directly)
MIGRATION_SQL = """
-- Create portfolio_timeseries table
CREATE TABLE IF NOT EXISTS portfolio_timeseries (
    id SERIAL PRIMARY KEY,
    client_code VARCHAR(20) NOT NULL REFERENCES bse_details(bse_client_code),
    date DATE NOT NULL,
    portfolio_value NUMERIC(15, 2) NOT NULL,
    invested_value NUMERIC(15, 2),
    day_change NUMERIC(15, 2),
    day_change_pct NUMERIC(10, 4),
    cumulative_return_pct NUMERIC(10, 4),
    holdings_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(client_code, date)
);

CREATE INDEX idx_portfolio_ts_client_date ON portfolio_timeseries(client_code, date DESC);
CREATE INDEX idx_portfolio_ts_date ON portfolio_timeseries(date DESC);

-- Create portfolio_holdings_snapshot table
CREATE TABLE IF NOT EXISTS portfolio_holdings_snapshot (
    id SERIAL PRIMARY KEY,
    client_code VARCHAR(20) NOT NULL REFERENCES bse_details(bse_client_code),
    date DATE NOT NULL,
    isin VARCHAR(12) NOT NULL REFERENCES mf_fund(isin),
    quantity NUMERIC(15, 4) NOT NULL,
    nav NUMERIC(10, 4) NOT NULL,
    value NUMERIC(15, 2) NOT NULL,
    UNIQUE(client_code, date, isin)
);

CREATE INDEX idx_holdings_snapshot_client_date ON portfolio_holdings_snapshot(client_code, date DESC);

-- Create transactions table (if not exists)
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    client_code VARCHAR(20) NOT NULL REFERENCES bse_details(bse_client_code),
    isin VARCHAR(12) NOT NULL REFERENCES mf_fund(isin),
    folio_no VARCHAR(20),
    transaction_date DATE NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    units NUMERIC(15, 4) NOT NULL,
    nav NUMERIC(10, 4) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    remarks VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transactions_client_date ON transactions(client_code, transaction_date DESC);
CREATE INDEX idx_transactions_isin_date ON transactions(isin, transaction_date DESC);
"""
