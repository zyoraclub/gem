from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gem_automation.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_db():
    """Add missing columns to existing tables"""
    with engine.connect() as conn:
        # Check and add user_id to oauth_tokens
        try:
            conn.execute(text("ALTER TABLE oauth_tokens ADD COLUMN user_id INTEGER"))
            conn.commit()
            print("[Migration] Added user_id to oauth_tokens")
        except:
            pass  # Column already exists
        
        # Check and add user_id to connected_sheets
        try:
            conn.execute(text("ALTER TABLE connected_sheets ADD COLUMN user_id INTEGER"))
            conn.commit()
            print("[Migration] Added user_id to connected_sheets")
        except:
            pass  # Column already exists


def init_db():
    Base.metadata.create_all(bind=engine)
    migrate_db()
