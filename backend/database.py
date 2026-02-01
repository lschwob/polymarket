from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, Text
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

class Trade(Base):
    __tablename__ = "trade"
    
    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("tracked_market.id"), index=True)
    outcome_id = Column(Integer, ForeignKey("outcome.id"), nullable=True, index=True)
    token_id = Column(String, index=True)  # Token ID from CLOB API
    user_address = Column(String, nullable=True)  # Anonymized user address
    amount = Column(Float)  # Trade amount
    price = Column(Float)  # Trade price
    side = Column(String)  # "buy" or "sell"
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    trade_id = Column(String, unique=True, nullable=True)  # External trade ID
    
    market = relationship("TrackedMarket")
    outcome = relationship("Outcome")

class PriceSnapshot(Base):
    __tablename__ = "price_snapshot"
    
    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("tracked_market.id"), index=True)
    outcome_id = Column(Integer, ForeignKey("outcome.id"), nullable=True, index=True)
    token_id = Column(String, index=True)  # Token ID from CLOB API
    price = Column(Float)  # Price at this snapshot
    volume = Column(Float, nullable=True)  # Volume at this snapshot
    open_price = Column(Float, nullable=True)  # OHLC data
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    interval = Column(String)  # "1m", "5m", "1h", "1d"
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    market = relationship("TrackedMarket")
    outcome = relationship("Outcome")

class OrderBookSnapshot(Base):
    __tablename__ = "order_book_snapshot"
    
    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("tracked_market.id"), index=True)
    outcome_id = Column(Integer, ForeignKey("outcome.id"), nullable=True, index=True)
    token_id = Column(String, index=True)  # Token ID from CLOB API
    bids = Column(JSON)  # List of bid orders [{price, size}, ...]
    asks = Column(JSON)  # List of ask orders [{price, size}, ...]
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    market = relationship("TrackedMarket")
    outcome = relationship("Outcome")


class TrackedUser(Base):
    __tablename__ = "tracked_user"
    
    address = Column(String, primary_key=True, index=True)  # Ethereum address (proxy wallet)
    name = Column(String, nullable=True)
    pseudonym = Column(String, nullable=True)
    profile_image = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    activities = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan")


class UserActivity(Base):
    __tablename__ = "user_activity"
    
    id = Column(Integer, primary_key=True, index=True)
    user_address = Column(String, ForeignKey("tracked_user.address"), index=True)
    activity_type = Column(String, index=True)  # TRADE, REDEEM
    market_id = Column(Integer, ForeignKey("tracked_market.id"), nullable=True, index=True)
    market_slug = Column(String, index=True)
    market_title = Column(String, nullable=True)
    outcome = Column(String, nullable=True)
    side = Column(String, nullable=True)  # BUY, SELL (null for REDEEM)
    size = Column(Float)  # tokens
    usdc_size = Column(Float)  # USDC value
    price = Column(Float, nullable=True)  # null for REDEEM
    timestamp = Column(DateTime, index=True)
    transaction_hash = Column(String, unique=True, index=True)
    
    user = relationship("TrackedUser", back_populates="activities")
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
