# -*- coding: utf-8 -*-
"""
Khởi tạo cơ sở dữ liệu SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Kết nối SQLite với check_same_thread=False cho FastAPI đa luồng
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency cung cấp Session Database cho FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

