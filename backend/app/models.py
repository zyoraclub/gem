from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.database import Base


class User(Base):
    """User accounts for multi-user support"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(Text)
    name = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    oauth_tokens = relationship("OAuthToken", back_populates="user")
    connected_sheets = relationship("ConnectedSheet", back_populates="user")


class OAuthToken(Base):
    """Store OAuth tokens for Gmail and Google Sheets"""
    __tablename__ = "oauth_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    service = Column(String(50), index=True)  # 'gmail' or 'sheets'
    email = Column(String(255))
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expiry = Column(DateTime)
    scopes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="oauth_tokens")


class GemAccount(Base):
    """GEM login accounts for rotation"""
    __tablename__ = "gem_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    password_encrypted = Column(Text)
    gmail_email = Column(String(255))  # Gmail for OTP
    is_active = Column(Boolean, default=True)
    daily_upload_count = Column(Integer, default=0)
    daily_limit = Column(Integer, default=10)
    last_used_at = Column(DateTime)
    last_reset_date = Column(Date, default=date.today)
    status = Column(String(50), default="READY")  # READY, IN_USE, EXHAUSTED, ERROR
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Settings(Base):
    """Application settings"""
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True)
    value = Column(Text)
    description = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConnectedSheet(Base):
    """Connected Google Sheets"""
    __tablename__ = "connected_sheets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sheet_id = Column(String(255), index=True)
    sheet_name = Column(String(255))
    sheet_url = Column(Text)
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="connected_sheets")


class PriceHistory(Base):
    """Track product price changes"""
    __tablename__ = "price_history"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(100), index=True)
    product_url = Column(Text)
    category_slug = Column(String(255))
    old_price = Column(Float)
    new_price = Column(Float)
    change_percent = Column(Float)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class UploadJob(Base):
    """Track upload jobs"""
    __tablename__ = "upload_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(100))
    sheet_id = Column(String(255))
    account_id = Column(Integer)
    status = Column(String(50), default="PENDING")  # PENDING, IN_PROGRESS, DONE, FAILED
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScrapeStats(Base):
    """Track scraping statistics"""
    __tablename__ = "scrape_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    stat_date = Column(Date, default=date.today, index=True)
    total_products_scraped = Column(Integer, default=0)
    total_categories_scraped = Column(Integer, default=0)
    price_changes_detected = Column(Integer, default=0)
    new_products_found = Column(Integer, default=0)
    products_updated = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OverallStats(Base):
    """Track overall lifetime statistics"""
    __tablename__ = "overall_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True)
    value = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
