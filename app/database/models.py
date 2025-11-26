from app.database.setup import db
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, UniqueConstraint, BigInteger
from sqlalchemy.orm import relationship

class Fund(db.Model):
    __tablename__ = 'mf_fund'
    
    isin = Column(String, primary_key=True)
    scheme_name = Column(String)
    amc_name = Column(String)
    fund_type = Column(String)
    scheme_code = Column(String)
    
    # Relationships
    nav_history = relationship("NavHistory", back_populates="fund", cascade="all, delete-orphan")
    returns = relationship("FundReturns", back_populates="fund", uselist=False, cascade="all, delete-orphan")

class NavHistory(db.Model):
    __tablename__ = 'mf_nav_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    isin = Column(String, ForeignKey('mf_fund.isin'), nullable=False)
    date = Column(Date, nullable=False)
    nav = Column(Float, nullable=False)
    
    fund = relationship("Fund", back_populates="nav_history")
    
    __table_args__ = (
        UniqueConstraint('isin', 'date', name='uq_mf_nav_history_isin_date'),
    )

class FundReturns(db.Model):
    __tablename__ = 'mf_returns'
    
    isin = Column(String, ForeignKey('mf_fund.isin'), primary_key=True)
    
    # Absolute Returns
    return_1m = Column(Float)
    return_3m = Column(Float)
    return_6m = Column(Float)
    return_ytd = Column(Float)
    return_1y = Column(Float)
    return_3y = Column(Float)
    return_5y = Column(Float)
    
    # CAGR Returns
    return_3y_carg = Column(Float)
    return_5y_carg = Column(Float)
    return_10y_carg = Column(Float)
    
    # Inception
    return_since_inception = Column(Float)
    return_since_inception_carg = Column(Float)
    
    fund = relationship("Fund", back_populates="returns")

# Placeholder classes for other imports seen in legacy.py
# These might not be fully used but are imported
class FundFactSheet(db.Model):
    __tablename__ = 'mf_fund_fact_sheet'
    id = Column(Integer, primary_key=True)
    isin = Column(String, ForeignKey('mf_fund.isin'))
    # Add other fields if known, for now minimal to satisfy imports

class FundHolding(db.Model):
    __tablename__ = 'mf_fund_holding'
    id = Column(Integer, primary_key=True)
    isin = Column(String, ForeignKey('mf_fund.isin'))
    # Add other fields if known

class BSEScheme(db.Model):
    __tablename__ = 'bse_scheme'
    scheme_code = Column(String, primary_key=True)
    isin = Column(String)
