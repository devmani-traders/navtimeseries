from app.database.setup import db
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint, BigInteger, Index, CheckConstraint, Text
from sqlalchemy.orm import relationship
from datetime import datetime

class Fund(db.Model):
    __tablename__ = 'mf_fund'
    
    isin = Column(String(12), primary_key=True)
    scheme_name = Column(String(255), nullable=False)
    fund_type = Column(String(50), nullable=False)  # Type (equity, debt, hybrid)
    fund_subtype = Column(String(100), nullable=True)  # Subtype
    amc_name = Column(String(100), nullable=False)  # Fund house name
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_fund_amc_name', 'amc_name'),  # Optimize AMC lookups
        Index('idx_fund_type', 'fund_type'),  # Optimize fund type lookups
    )
    
class FundFactSheet(db.Model):
    """
    Enhanced factsheet information for a mutual fund.
    Supports Excel columns from AMC factsheets.
    """
    __tablename__ = 'mf_factsheet'

    isin = Column(String(12),
                     ForeignKey('mf_fund.isin'),
                     primary_key=True)

    # Core fund information
    scheme_name = Column(String(255), nullable=True)
    scheme_type = Column(String(100), nullable=True)
    sub_category = Column(String(100), nullable=True)
    plan = Column(String(50), nullable=True)
    amc = Column(String(100), nullable=True)

    # Financial details
    expense_ratio = Column(Float, nullable=True)
    minimum_lumpsum = Column(Float, nullable=True)
    minimum_sip = Column(Float, nullable=True)
    min_additional_purchase = Column(Float, nullable=True) # Additional to current fields 
    aum = Column(Float, nullable=True)  # Assets Under Management

    # Investment terms
    lock_in = Column(String(100), nullable=True)
    exit_load = Column(Text, nullable=True)      ## Additional to current fields 

    # Management and risk
    fund_manager = Column(String(255), nullable=True)
    benchmark = Column(String(255), nullable=True)
    benchmark_isin = Column(String(12), nullable=True)  # Additional to current fields    
    sebi_risk_category = Column(String(50), nullable=True)
    riskometer_launch = Column(String(100), nullable=True)   # Additional to current fields 

    # Descriptive fields
    investment_objective = Column(Text, nullable=True) # Additional to current fields 
    asset_allocation = Column(Text, nullable=True)  # Additional to current fields 

    # Dates
    launch_date = Column(Date, nullable=True)  # Legacy
    nfo_open_date = Column(Date, nullable=True)   # Additional to current fields 
    nfo_close_date = Column(Date, nullable=True)   # Additional to current fields 
    reopen_date = Column(Date, nullable=True)       # Additional to current fields 
    allotment_date = Column(Date, nullable=True)     # Additional to current fields 

    # Metadata and external entities
    custodian = Column(String(255), nullable=True)     # Additional to current fields 
    auditor = Column(String(255), nullable=True)        # Additional to current fields 
    rta = Column(String(255), nullable=True)           # Additional to current fields 
    isin_list = Column(Text, nullable=True)             # Additional to current fields 
    sebi_registration_number = Column(String(100), nullable=True)   # Additional to current fields 
    scheme_code = Column(String(100), nullable=True)                 # Additional to current fields AMFI scheme code

    # Timestamps
    last_updated = Column(DateTime,
                             default=datetime.utcnow,
                             onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to main fund table
    fund = db.relationship("Fund", backref="factsheet")

    __table_args__ = (
        Index('idx_factsheet_scheme_type', 'scheme_type'),
        Index('idx_factsheet_sub_category', 'sub_category'),
        Index('idx_factsheet_amc', 'amc'),
        Index('idx_factsheet_sebi_risk', 'sebi_risk_category'),
    )

class FundReturns(db.Model):
    """
    Returns data for a mutual fund
    """
    __tablename__ = 'mf_returns'

    isin = Column(String(12),
                     ForeignKey('mf_fund.isin'),
                     primary_key=True)
    return_1m = Column(Float, nullable=True)  # 1-month return percentage
    return_3m = Column(Float, nullable=True)  # 3-month return percentage
    return_6m = Column(Float, nullable=True)  # 6-month return percentage
    return_ytd = Column(Float,nullable=True)  # Year-to-date return percentage
    return_1y = Column(Float, nullable=True)  # 1-year return percentage
    return_3y = Column(Float, nullable=True)  # 3-year return percentage
    return_5y = Column(Float, nullable=True)  # 5-year return percentage
    return_3y_carg = Column(Float, nullable=True)  # 3-year return percentage
    return_5y_carg = Column(Float, nullable=True)  # 5-year return percentage
    return_10y_carg = Column(Float, nullable=True)  # 10-year return percentage
    return_since_inception = Column(Float, nullable=True)  # Since inception return percentage
    return_since_inception_carg = Column(Float, nullable=True)  # Since inception return percentage

    last_updated = Column(DateTime,
                             default=datetime.utcnow,
                             onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to Fund
    fund = relationship("Fund", backref="returns")

    __table_args__ = (
        CheckConstraint('return_1m >= -100', name='check_return_1m'),
        CheckConstraint('return_3m >= -100', name='check_return_3m'),
        CheckConstraint('return_6m >= -100', name='check_return_6m'),
        CheckConstraint('return_ytd >= -100', name='check_return_ytd'),
        CheckConstraint('return_1y >= -100', name='check_return_1y'),
        CheckConstraint('return_3y >= -100', name='check_return_3y'),
        CheckConstraint('return_5y >= -100', name='check_return_5y'),
    )


class FundHolding(db.Model):
    """
    Holdings/investments within a mutual fund
    Expected columns: Name of Instrument, ISIN, Coupon, Industry, Quantity, 
    Market Value, % to Net Assets, Yield, Type, AMC, Scheme Name, Scheme ISIN
    """
    __tablename__ = 'mf_fund_holdings'

    id = Column(Integer, primary_key=True)
    isin = Column(String(12),
                     ForeignKey('mf_fund.isin'),
                     nullable=False)  # Scheme ISIN
    instrument_isin = Column(String(12),
                                nullable=False)  # ISIN of the instrument
    coupon = Column(Float,
                       nullable=True)  # Coupon percentage for debt instruments
    instrument_name = Column(String(255),
                                nullable=False)  # Name of Instrument
    sector = Column(String(255),
                       nullable=True)  # Industry classification
    quantity = Column(Float, nullable=True)  # Quantity held
    value = Column(Float, nullable=True)  # Market Value in INR
    percentage_to_nav = Column(Float, nullable=False)  # % to Net Assets
    yield_value = Column(Float, nullable=True)  # Yield percentage
    instrument_type = Column(String(100),
                                nullable=False)  # Type of instrument
    amc_name = Column(String(255), nullable=True)  # AMC name from upload
    scheme_name = Column(String(255),
                            nullable=False)  # Scheme Name from upload
    last_updated = Column(DateTime,
                             default=datetime.utcnow,
                             onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to Fund
    fund = relationship("Fund", backref="fund_holdings")

    __table_args__ = (
        UniqueConstraint('isin', 'instrument_isin', name='uix_schemeisin_instrumentisin'),
        CheckConstraint('percentage_to_nav >= 0',
                        name='check_percentage_to_nav'),
        CheckConstraint('percentage_to_nav <= 100',
                        name='check_percentage_to_nav_upper'),
    )


class NavHistory(db.Model):
    """
    NAV history for a mutual fund
    """
    __tablename__ = 'mf_nav_history'

    id = Column(Integer, primary_key=True)
    isin = Column(String(12),
                     ForeignKey('mf_fund.isin'),
                     nullable=False)
    date = Column(Date, nullable=False)  # Date of NAV
    nav = Column(Float, nullable=False)  # NAV value
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime,
                           default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    # Relationship to Fund
    fund = relationship("Fund", backref="nav_history")

    __table_args__ = (
        CheckConstraint('nav >= 0', name='check_nav'),
        Index('idx_nav_history_isin_date', 'isin', 'date', unique=True),
    )