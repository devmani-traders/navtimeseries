from app.database.setup import db
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint, BigInteger, Index, CheckConstraint
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

    isin = db.Column(db.String(12),
                     db.ForeignKey('mf_fund.isin'),
                     primary_key=True)

    # Core fund information
    scheme_name = db.Column(db.String(255), nullable=True)
    scheme_type = db.Column(db.String(100), nullable=True)
    sub_category = db.Column(db.String(100), nullable=True)
    plan = db.Column(db.String(50), nullable=True)
    amc = db.Column(db.String(100), nullable=True)

    # Financial details
    expense_ratio = db.Column(db.Float, nullable=True)
    minimum_lumpsum = db.Column(db.Float, nullable=True)
    minimum_sip = db.Column(db.Float, nullable=True)
    min_additional_purchase = db.Column(db.Float, nullable=True) # Additional to current fields 
    aum = db.Column(db.Float, nullable=True)  # Assets Under Management

    # Investment terms
    lock_in = db.Column(db.String(100), nullable=True)
    exit_load = db.Column(db.Text, nullable=True)      ## Additional to current fields 

    # Management and risk
    fund_manager = db.Column(db.String(255), nullable=True)
    benchmark = db.Column(db.String(255), nullable=True)
    benchmark_isin = db.Column(db.String(12), nullable=True)  # Additional to current fields    
    sebi_risk_category = db.Column(db.String(50), nullable=True)
    riskometer_launch = db.Column(db.String(100), nullable=True)   # Additional to current fields 

    # Descriptive fields
    investment_objective = db.Column(db.Text, nullable=True) # Additional to current fields 
    asset_allocation = db.Column(db.Text, nullable=True)  # Additional to current fields 

    # Dates
    launch_date = db.Column(db.Date, nullable=True)  # Legacy
    nfo_open_date = db.Column(db.Date, nullable=True)   # Additional to current fields 
    nfo_close_date = db.Column(db.Date, nullable=True)   # Additional to current fields 
    reopen_date = db.Column(db.Date, nullable=True)       # Additional to current fields 
    allotment_date = db.Column(db.Date, nullable=True)     # Additional to current fields 

    # Metadata and external entities
    custodian = db.Column(db.String(255), nullable=True)     # Additional to current fields 
    auditor = db.Column(db.String(255), nullable=True)        # Additional to current fields 
    rta = db.Column(db.String(255), nullable=True)           # Additional to current fields 
    isin_list = db.Column(db.Text, nullable=True)             # Additional to current fields 
    sebi_registration_number = db.Column(db.String(100), nullable=True)   # Additional to current fields 
    scheme_code = db.Column(db.String(100), nullable=True)                 # Additional to current fields AMFI scheme code

    # Timestamps
    last_updated = db.Column(db.DateTime,
                             default=datetime.utcnow,
                             onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

    isin = db.Column(db.String(12),
                     db.ForeignKey('mf_fund.isin'),
                     primary_key=True)
    return_1m = db.Column(db.Float, nullable=True)  # 1-month return percentage
    return_3m = db.Column(db.Float, nullable=True)  # 3-month return percentage
    return_6m = db.Column(db.Float, nullable=True)  # 6-month return percentage
    return_ytd = db.Column(db.Float,nullable=True)  # Year-to-date return percentage
    return_1y = db.Column(db.Float, nullable=True)  # 1-year return percentage
    return_3y = db.Column(db.Float, nullable=True)  # 3-year return percentage
    return_5y = db.Column(db.Float, nullable=True)  # 5-year return percentage
    return_3y_carg = db.Column(db.Float, nullable=True)  # 3-year return percentage
    return_5y_carg = db.Column(db.Float, nullable=True)  # 5-year return percentage
    return_10y_carg = db.Column(db.Float, nullable=True)  # 10-year return percentage
    return_since_inception = db.Column(db.Float, nullable=True)  # Since inception return percentage
    return_since_inception_carg = db.Column(db.Float, nullable=True)  # Since inception return percentage

    last_updated = db.Column(db.DateTime,
                             default=datetime.utcnow,
                             onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to Fund
    fund = db.relationship("Fund", backref="returns")

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

    id = db.Column(db.Integer, primary_key=True)
    isin = db.Column(db.String(12),
                     db.ForeignKey('mf_fund.isin'),
                     nullable=False)  # Scheme ISIN
    instrument_isin = db.Column(db.String(12),
                                nullable=False)  # ISIN of the instrument
    coupon = db.Column(db.Float,
                       nullable=True)  # Coupon percentage for debt instruments
    instrument_name = db.Column(db.String(255),
                                nullable=False)  # Name of Instrument
    sector = db.Column(db.String(255),
                       nullable=True)  # Industry classification
    quantity = db.Column(db.Float, nullable=True)  # Quantity held
    value = db.Column(db.Float, nullable=True)  # Market Value in INR
    percentage_to_nav = db.Column(db.Float, nullable=False)  # % to Net Assets
    yield_value = db.Column(db.Float, nullable=True)  # Yield percentage
    instrument_type = db.Column(db.String(100),
                                nullable=False)  # Type of instrument
    amc_name = db.Column(db.String(255), nullable=True)  # AMC name from upload
    scheme_name = db.Column(db.String(255),
                            nullable=False)  # Scheme Name from upload
    last_updated = db.Column(db.DateTime,
                             default=datetime.utcnow,
                             onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to Fund
    fund = db.relationship("Fund", backref="fund_holdings")

    __table_args__ = (
        db.UniqueConstraint('isin', 'instrument_isin', name='uix_schemeisin_instrumentisin'),
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

    id = db.Column(db.Integer, primary_key=True)
    isin = db.Column(db.String(12),
                     db.ForeignKey('mf_fund.isin'),
                     nullable=False)
    date = db.Column(db.Date, nullable=False)  # Date of NAV
    nav = db.Column(db.Float, nullable=False)  # NAV value
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    # Relationship to Fund
    fund = db.relationship("Fund", backref="nav_history")

    __table_args__ = (
        CheckConstraint('nav >= 0', name='check_nav'),
        Index('idx_nav_history_isin_date', 'isin', 'date', unique=True),
    )