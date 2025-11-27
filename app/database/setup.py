import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, registry
from app import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Create base metadata
metadata = MetaData(naming_convention=convention)

# Create SQLAlchemy base class
class Base(DeclarativeBase):
    metadata = metadata

# Create SQLAlchemy extension
db = SQLAlchemy(model_class=Base)

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)

    # Database Configuration
    database_uri = config.DB_URL
    
    if not database_uri:
        raise ValueError("Database URL not found in config")

    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "connect_args": {
            "connect_timeout": 30,
            "sslmode": "require"
        }
    }

    app.secret_key = 'dev'
    
    # Initialize database
    db.init_app(app)
    
    return app
