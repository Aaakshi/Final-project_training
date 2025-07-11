from sqlalchemy import Column, String, Float, JSON, Integer, ARRAY, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_name = Column(String(255), nullable=False)
    storage_path = Column(String, nullable=False)
    doc_type = Column(String(50))
    confidence = Column(Float)

class Metadata(Base):
    __tablename__ = "metadata"
    meta_id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(UUID(as_uuid=True), nullable=False)
    key_entities = Column(JSON)
    related_docs = Column(ARRAY(UUID(as_uuid=True)))
    risk_score = Column(Float)

class RoutingRule(Base):
    __tablename__ = "routing_rules"
    rule_id = Column(Integer, primary_key=True, autoincrement=True)
    condition = Column(JSON)
    assignee = Column(String(100))
    priority = Column(Integer)