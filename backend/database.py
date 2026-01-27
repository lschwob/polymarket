from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class TrendingCategoryCache(Base):
    __tablename__ = "trending_category_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    label = Column(String)
    score = Column(Float)
    computed_at = Column(DateTime, default=datetime.utcnow)

class TrackedMarket(Base):
    __tablename__ = "tracked_market"
    
    id = Column(Integer, primary_key=True, index=True)
    market_slug = Column(String, index=True)
    market_id = Column(String, index=True)
    title = Column(String)
    tag_slug = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    outcomes = relationship("Outcome", back_populates="market", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="market", cascade="all, delete-orphan")

class Outcome(Base):
    __tablename__ = "outcome"
    
    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("tracked_market.id"))
    outcome_id = Column(String, index=True)
    name = Column(String)
    
    market = relationship("TrackedMarket", back_populates="outcomes")
    snapshots = relationship("Snapshot", back_populates="outcome", cascade="all, delete-orphan")

class Snapshot(Base):
    __tablename__ = "snapshot"
    
    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("tracked_market.id"))
    outcome_id = Column(Integer, ForeignKey("outcome.id"))
    prob = Column(Float)
    volume = Column(Float, nullable=True)
    liquidity = Column(Float, nullable=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    
    market = relationship("TrackedMarket", back_populates="snapshots")
    outcome = relationship("Outcome", back_populates="snapshots")

class Alert(Base):
    __tablename__ = "alert"
    
    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("tracked_market.id"))
    outcome_id = Column(Integer, ForeignKey("outcome.id"), nullable=True)
    prev_prob = Column(Float)
    new_prob = Column(Float)
    delta = Column(Float)
    delta_percent = Column(Float)
    volume = Column(Float, nullable=True)  # Volume au moment du shift
    volume_impact = Column(Float, nullable=True)  # Impact quantifié (delta * volume)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String, default="active")  # active, acknowledged
    
    market = relationship("TrackedMarket")

# SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///./polymarket_tracker.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
