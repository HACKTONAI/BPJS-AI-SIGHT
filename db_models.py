from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///data.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Visit(Base):
    __tablename__ = "visits"
    id = Column(Integer, primary_key=True, index=True)
    ds = Column(Date, index=True)
    y = Column(Integer)
    nama_faskes = Column(String, index=True)
    kapasitas = Column(Integer)
    jarak = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class Forecast(Base):
    __tablename__ = "forecasts"
    id = Column(Integer, primary_key=True, index=True)
    nama_faskes = Column(String, index=True)
    ds = Column(Date, index=True)  # tanggal forecast (target)
    yhat = Column(Float)
    yhat_lower = Column(Float)
    yhat_upper = Column(Float)
    generated_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("DB initialized: data.db")
