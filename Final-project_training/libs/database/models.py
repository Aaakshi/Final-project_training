
from sqlalchemy import Column, String, Float, JSON, Integer, DateTime, Text, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    
    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt, xlsx
    mime_type = Column(String(100), nullable=False)
    
    # Upload metadata
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(String(100), default="system")
    
    # Processing status
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    
    # OCR and content
    extracted_text = Column(Text)
    ocr_confidence = Column(Float)
    
    # Classification results
    document_type = Column(String(100))  # invoice, contract, report, etc.
    department = Column(String(100))     # finance, legal, hr, etc.
    priority = Column(String(50))        # high, medium, low
    classification_confidence = Column(Float)
    
    # Additional metadata
    page_count = Column(Integer)
    language = Column(String(10))
    tags = Column(JSON)
    
    def to_dict(self):
        return {
            'doc_id': str(self.doc_id),
            'original_name': self.original_name,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'processing_status': self.processing_status,
            'document_type': self.document_type,
            'department': self.department,
            'priority': self.priority,
            'classification_confidence': self.classification_confidence,
            'page_count': self.page_count,
            'tags': self.tags
        }

class ProcessingLog(Base):
    __tablename__ = "processing_logs"
    
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), nullable=False)
    processing_step = Column(String(100), nullable=False)  # upload, ocr, classify, route
    status = Column(String(50), nullable=False)  # started, completed, failed
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON)
    error_message = Column(Text)

class UploadBatch(Base):
    __tablename__ = "upload_batches"
    
    batch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_name = Column(String(255))
    total_files = Column(Integer, nullable=False)
    processed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(50), default="processing")  # processing, completed, failed
