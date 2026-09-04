from __future__ import annotations
import datetime as dt
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class Case(Base):
    __tablename__ = "cases"
    id = Column(Integer, primary_key=True)
    sahyog_case_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    status = Column(String, default="open")

    addresses = relationship("Address", back_populates="case")
    reports = relationship("Report", back_populates="case")


class Address(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    address = Column(String, nullable=False, index=True)
    chain = Column(String, nullable=False)
    role = Column(String, nullable=True)

    case = relationship("Case", back_populates="addresses")


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    tx_hash = Column(String, nullable=False, index=True)
    chain = Column(String, nullable=False)
    from_address = Column(String, nullable=False, index=True)
    to_address = Column(String, nullable=False, index=True)
    value = Column(Float, nullable=False)
    token = Column(String, nullable=True)
    token_contract = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    block_number = Column(Integer, nullable=False)
    tx_type_raw = Column(String, nullable=False, default="unknown")
    gas_used = Column(Float, nullable=True)


class Label(Base):
    __tablename__ = "labels"
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False, index=True)
    chain = Column(String, nullable=False)
    label_type = Column(String, nullable=False)
    label_value = Column(String, nullable=False)
    source = Column(String, nullable=True)


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    generated_at = Column(DateTime, default=dt.datetime.utcnow)
    confidence_score = Column(Float, nullable=True)
    confidence_band = Column(String, nullable=True)
    content_json = Column(Text, nullable=False)
    cert_hash = Column(String, nullable=True)

    case = relationship("Case", back_populates="reports")


DATABASE_URL = "sqlite:///./vasp.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def init_db():
    Base.metadata.create_all(bind=engine)