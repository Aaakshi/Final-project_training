import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
import uuid
import shutil
from pathlib import Path
import logging
from typing import List, Optional
import json
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./idcr_documents.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# FastAPI app
app = FastAPI(title="IDCR Document Management System")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    department = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String, unique=True, index=True)
    original_name = Column(String)
    file_path = Column(String)
    document_type = Column(String)
    department = Column(String)
    priority = Column(String)
    processing_status = Column(String, default="uploaded")
    review_status = Column(String, default="pending")
    uploaded_by = Column(String)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    classification_confidence = Column(Float)
    page_count = Column(Integer)
    tags = Column(Text)

class EmailNotification(Base):
    __tablename__ = "email_notifications"

    id = Column(Integer, primary_key=True, index=True)
    sent_by = Column(String)
    sent_by_name = Column(String)
    received_by = Column(String)
    received_by_name = Column(String)
    subject = Column(String)
    body_preview = Column(Text)
    email_type = Column(String)  # sent, received
    document_name = Column(String)
    document_type = Column(String)
    department = Column(String)
    priority = Column(String)
    status = Column(String, default="sent")
    sent_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic models
class UserCreate(BaseModel):
    full_name: str
    email: str
    password: str
    department: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(email: str = Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return FileResponse("Final-project_training/index.html")

@app.post("/api/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password,
        department=user.department
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {"message": "User created successfully"}

@app.post("/api/login", response_model=Token)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": db_user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "full_name": db_user.full_name,
            "email": db_user.email,
            "department": db_user.department
        }
    }

@app.get("/api/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "department": current_user.department
    }

@app.get("/api/stats")
async def get_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        total_docs = db.query(Document).count()
        processed_docs = db.query(Document).filter(Document.processing_status == "completed").count()
        pending_docs = db.query(Document).filter(Document.review_status == "pending").count()
        error_docs = db.query(Document).filter(Document.processing_status == "failed").count()

        processing_rate = (processed_docs / total_docs * 100) if total_docs > 0 else 0

        return {
            "total_documents": total_docs,
            "processed_documents": processed_docs,
            "pending_documents": pending_docs,
            "error_documents": error_docs,
            "processing_rate": round(processing_rate, 1),
            "document_types": {},
            "departments": {},
            "priorities": {},
            "upload_trends": []
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            "total_documents": 0,
            "processed_documents": 0,
            "pending_documents": 0,
            "error_documents": 0,
            "processing_rate": 0,
            "document_types": {},
            "departments": {},
            "priorities": {},
            "upload_trends": []
        }

@app.post("/api/bulk-upload")
async def bulk_upload(
    batch_name: str = Form(...),
    target_department: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch_id = str(uuid.uuid4())
    upload_dir = Path(f"uploads/{batch_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)

    uploaded_files = []

    for file in files:
        # Save file
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Create document record
        doc_id = str(uuid.uuid4())
        document = Document(
            doc_id=doc_id,
            original_name=file.filename,
            file_path=str(file_path),
            document_type="general",
            department=target_department,
            priority="medium",
            uploaded_by=current_user.email
        )
        db.add(document)
        uploaded_files.append(file.filename)

    db.commit()
    logger.info(f"Uploaded {len(files)} files in batch {batch_name}")

    return {"message": f"Successfully uploaded {len(files)} files", "batch_id": batch_id}

@app.get("/api/documents")
async def get_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        documents = db.query(Document).all()
        doc_list = []
        for doc in documents:
            doc_list.append({
                "doc_id": doc.doc_id,
                "original_name": doc.original_name,
                "document_type": doc.document_type,
                "department": doc.department,
                "priority": doc.priority,
                "processing_status": doc.processing_status,
                "review_status": doc.review_status,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "uploaded_by": doc.uploaded_by
            })
        return {"documents": doc_list}
    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        return {"documents": []}

@app.get("/api/email-notifications")
async def get_email_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        emails = db.query(EmailNotification).order_by(EmailNotification.sent_at.desc()).limit(50).all()
        email_list = []
        for email in emails:
            email_list.append({
                "id": email.id,
                "sent_by": email.sent_by,
                "sent_by_name": email.sent_by_name,
                "received_by": email.received_by,
                "received_by_name": email.received_by_name,
                "subject": email.subject,
                "body_preview": email.body_preview,
                "email_type": email.email_type,
                "document_name": email.document_name,
                "document_type": email.document_type,
                "department": email.department,
                "priority": email.priority,
                "status": email.status,
                "sent_at": email.sent_at.isoformat() if email.sent_at else None
            })
        return {"emails": email_list}
    except Exception as e:
        logger.error(f"Error getting email notifications: {e}")
        return {"emails": []}

if __name__ == "__main__":
    logger.info("Database initialized")
    uvicorn.run(app, host="0.0.0.0", port=5000)