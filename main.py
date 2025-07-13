from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uvicorn
import sqlite3
import os
import hashlib
import uuid
import datetime
import jwt
import logging
import asyncio
import subprocess
import time
import json
import shutil
import threading
from pathlib import Path
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
import PyPDF2
import docx
from werkzeug.utils import secure_filename
import mimetypes
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import httpx
from datetime import timedelta

app = FastAPI(title="IDCR Enhanced Demo Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
SECRET_KEY = "your-secret-key-here"  # In production, use environment variable
ALGORITHM = "HS256"

# Email configuration (Outlook SMTP)
try:
    from email_config import EMAIL_CONFIG
    SMTP_SERVER = EMAIL_CONFIG["SMTP_SERVER"]
    SMTP_PORT = EMAIL_CONFIG["SMTP_PORT"]
    EMAIL_USER = EMAIL_CONFIG["EMAIL_USER"]
    EMAIL_PASSWORD = EMAIL_CONFIG["EMAIL_PASSWORD"]
except ImportError:
    # Fallback to default values
    SMTP_SERVER = "smtp-mail.outlook.com"
    SMTP_PORT = 587
    EMAIL_USER = "akshipersonal003@gmail.com"  # Replace with your Outlook email
    EMAIL_PASSWORD = "Akshi@2003"  # Replace with your app password

# Global variable to track backend processes
backend_processes = []

# Database setup
DB_PATH = "idcr_documents.db"


def init_database():
    """Initialize SQLite database for document storage and user management"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            department TEXT,
            role TEXT DEFAULT 'employee',
            created_at TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

    # Create departments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            dept_id TEXT PRIMARY KEY,
            dept_name TEXT NOT NULL,
            dept_email TEXT NOT NULL,
            manager_email TEXT
        )
    ''')

    # Insert default departments with dummy emails
    default_departments = [
        ('hr', 'Human Resources (HR)', 'hr@company.com', 'hr.manager@company.com'),
        ('finance', 'Finance & Accounting', 'finance@company.com', 'finance.manager@company.com'),
        ('legal', 'Legal', 'legal@company.com', 'legal.manager@company.com'),
        ('sales', 'Sales', 'sales@company.com', 'sales.manager@company.com'),
        ('marketing', 'Marketing', 'marketing@company.com', 'marketing.manager@company.com'),
        ('it', 'IT (Information Technology)', 'it@company.com', 'it.manager@company.com'),
        ('operations', 'Operations', 'operations@company.com', 'operations.manager@company.com'),
        ('support', 'Customer Support', 'support@company.com', 'support.manager@company.com'),
        ('procurement', 'Procurement / Purchase', 'procurement@company.com', 'procurement.manager@company.com'),
        ('product', 'Product / R&D', 'product@company.com', 'product.manager@company.com'),
        ('administration', 'Administration', 'administration@company.com', 'administration.manager@company.com'),
        ('executive', 'Executive / Management', 'executive@company.com', 'executive.manager@company.com'),
        ('general', 'General Department', 'general@company.com', 'general.manager@company.com')
    ]

    for dept in default_departments:
        cursor.execute(
            '''
            INSERT OR IGNORE INTO departments (dept_id, dept_name, dept_email, manager_email)
            VALUES (?, ?, ?, ?)
        ''', dept)

    # Create default demo users for each department
    demo_users = [
        ('hr.manager@company.com', 'HR Manager', 'hr', 'manager', 'password123'),
        ('hr.employee@company.com', 'HR Employee', 'hr', 'employee', 'password123'),
        ('finance.manager@company.com', 'Finance Manager', 'finance', 'manager', 'password123'),
        ('finance.employee@company.com', 'Finance Employee', 'finance', 'employee', 'password123'),
        ('legal.manager@company.com', 'Legal Manager', 'legal', 'manager', 'password123'),
        ('it.manager@company.com', 'IT Manager', 'it', 'manager', 'password123'),
        ('sales.manager@company.com', 'Sales Manager', 'sales', 'manager', 'password123'),
        ('general.employee@company.com', 'General Employee', 'general', 'employee', 'password123'),
        ('admin@company.com', 'System Admin', 'administration', 'admin', 'admin123')
    ]

    # Insert demo users and get their IDs
    user_ids = {}
    for email, name, dept, role, password in demo_users:
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute(
            '''
            INSERT OR IGNORE INTO users (user_id, email, password_hash, full_name, department, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, email, password_hash, name, dept, role, datetime.datetime.utcnow().isoformat()))
        user_ids[email] = user_id

    # Create sample documents for better statistics

    # Create sample priority documents first
    sample_priority_docs = [
        ('urgent_invoice.txt', 'hr.manager@company.com', 'finance', 'financial_document', 'high', 'classified', "urgent invoice payment"),
        ('reminder_contract.txt', 'hr.manager@company.com', 'legal', 'legal_document', 'medium', 'classified', "reminder contract terms"),
        ('fyi_report.txt', 'general.employee@company.com', 'general', 'general_document', 'low', 'classified', "fyi report summary"),
        ('hr_urgent_policy.txt', 'hr.manager@company.com', 'hr', 'hr_document', 'high', 'classified', "hr urgent policy update")
    ]

    for original_name, user_email, dept, doc_type, priority, status, content in sample_priority_docs:
        doc_id = str(uuid.uuid4())
        user_id = user_ids.get(user_email, user_ids['admin@company.com'])
        file_path = f"uploads/sample/{original_name}"
        file_size = 150000 + len(original_name) * 1000  # Simulate file size
        file_type = original_name.split('.')[-1].lower()
        mime_type = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'txt': 'text/plain'
        }.get(file_type, 'application/octet-stream')

        # Create sample document records
        cursor.execute('''
            INSERT OR IGNORE INTO documents (
                doc_id, user_id, original_name, file_path, file_size, file_type, 
                mime_type, uploaded_at, processing_status, document_type, department, 
                priority, classification_confidence, page_count, language, tags, 
                review_status, extracted_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_id, user_id, original_name, file_path, file_size, file_type,
            mime_type, datetime.datetime.utcnow().isoformat(), status, doc_type, dept,
            priority, 0.85, 1, 'en', '["' + doc_type + '", "' + dept + '"]',
            'approved' if status == 'approved' else 'pending', content
        ))

    sample_documents = [
        ('Invoice_2024_001.pdf', 'hr.manager@company.com', 'finance', 'financial_document', 'high', 'classified'),
        ('Employee_Handbook.pdf', 'hr.manager@company.com', 'hr', 'hr_document', 'medium', 'classified'),
        ('Contract_ABC_Corp.pdf', 'legal.manager@company.com', 'legal', 'legal_document', 'high', 'classified'),
        ('IT_Security_Policy.docx', 'it.manager@company.com', 'it', 'it_document', 'high', 'classified'),
        ('Sales_Report_Q4.xlsx', 'sales.manager@company.com', 'sales', 'sales_document', 'medium', 'classified'),
        ('Marketing_Campaign.pptx', 'finance.manager@company.com', 'marketing', 'marketing_document', 'medium', 'classified'),
        ('Expense_Report.pdf', 'general.employee@company.com', 'finance', 'financial_document', 'low', 'processing'),
        ('Meeting_Minutes.docx', 'hr.employee@company.com', 'hr', 'hr_document', 'low', 'classified'),
        ('Budget_Proposal.xlsx', 'finance.manager@company.com', 'finance', 'financial_document', 'high', 'classified'),
        ('Legal_Compliance.pdf', 'legal.manager@company.com', 'legal', 'legal_document', 'high', 'approved'),
    ]

    for original_name, user_email, dept, doc_type, priority, status in sample_documents:
        doc_id = str(uuid.uuid4())
        user_id = user_ids.get(user_email, user_ids['admin@company.com'])
        file_path = f"uploads/sample/{original_name}"
        file_size = 150000 + len(original_name) * 1000  # Simulate file size
        file_type = original_name.split('.')[-1].lower()
        mime_type = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        }.get(file_type, 'application/octet-stream')

        # Create sample document records
        cursor.execute('''
            INSERT OR IGNORE INTO documents (
                doc_id, user_id, original_name, file_path, file_size, file_type, 
                mime_type, uploaded_at, processing_status, document_type, department, 
                priority, classification_confidence, page_count, language, tags, 
                review_status, extracted_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_id, user_id, original_name, file_path, file_size, file_type,
            mime_type, datetime.datetime.utcnow().isoformat(), status, doc_type, dept,
            priority, 0.85, 1, 'en', '["' + doc_type + '", "' + dept + '"]',
            'approved' if status == 'approved' else 'pending',
            f"Sample content for {original_name} - This is a {doc_type} document for {dept} department."
        ))

    # Create documents table (updated with user info)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            processing_status TEXT DEFAULT 'pending',
            extracted_text TEXT,
            ocr_confidence REAL,
            document_type TEXT,
            department TEXT,
            priority TEXT,
            classification_confidence REAL,
            page_count INTEGER,
            language TEXT,
            tags TEXT,
            assigned_to TEXT,
            reviewed_by TEXT,
            review_status TEXT DEFAULT 'pending',
            review_comments TEXT,
            reviewed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Create upload batches table (updated)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS upload_batches (
            batch_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            batch_name TEXT,
            total_files INTEGER NOT NULL,
            processed_files INTEGER DEFAULT 0,
            failed_files INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT DEFAULT 'processing',
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Create notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            doc_id TEXT,
            message TEXT NOT NULL,
            type TEXT NOT NULL,
            read_status BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (doc_id) REFERENCES documents (doc_id)
        )
    ''')

    # Create email_notifications table for tracking emails
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_notifications (
            email_id TEXT PRIMARY KEY,
            sent_by TEXT NOT NULL,
            received_by TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT,
            doc_id TEXT,
            file_name TEXT,
            status TEXT DEFAULT 'sent',
            sent_at TEXT NOT NULL,
            read_at TEXT,
            FOREIGN KEY (doc_id) REFERENCES documents (doc_id)
        )
    ''')

    # Check if user_id column exists in documents table, add if missing
    cursor.execute("PRAGMA table_info(documents)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'user_id' not in columns:
        cursor.execute(
            'ALTER TABLE documents ADD COLUMN user_id TEXT DEFAULT "system"')

    # Check if user_id column exists in upload_batches table, add if missing
    cursor.execute("PRAGMA table_info(upload_batches)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'user_id' not in columns:
        cursor.execute(
            'ALTER TABLE upload_batches ADD COLUMN user_id TEXT DEFAULT "system"'
        )

    # Add comprehensive sample email notifications for demo
    sample_emails = [
        # HR Department emails
        ('hr.manager@company.com', 'hr@company.com', 'New HR Document Uploaded - Employee_Handbook.pdf', 
         '<html><body><h2>New Document Uploaded</h2><p>Employee_Handbook.pdf has been uploaded and classified to HR department.</p><p><strong>Priority:</strong> Medium</p><p><strong>Type:</strong> HR Document</p></body></html>',
         None, 'Employee_Handbook.pdf'),
        ('hr.employee@company.com', 'hr.manager@company.com', 'Document Review Request - Meeting_Minutes.docx', 
         '<html><body><h2>Document Review Required</h2><p>Meeting_Minutes.docx uploaded by HR Employee requires review.</p><p><strong>Priority:</strong> Low</p></body></html>',
         None, 'Meeting_Minutes.docx'),
        ('hr.manager@company.com', 'hr.employee@company.com', 'Document Approved - Meeting_Minutes.docx', 
         '<html><body><h2>Document Review Complete</h2><p>Your document Meeting_Minutes.docx has been approved.</p><p><strong>Reviewed by:</strong> HR Manager</p></body></html>',
         None, 'Meeting_Minutes.docx'),

        # Finance Department emails
        ('hr.manager@company.com', 'finance@company.com', 'New Financial Document for Review - Invoice_2024_001.pdf', 
         '<html><body><h2>New Document Uploaded for Review</h2><p>Invoice_2024_001.pdf has been uploaded and classified to finance department.</p><p><strong>Priority:</strong> High</p><p><strong>Type:</strong> Financial Document</p></body></html>',
         None, 'Invoice_2024_001.pdf'),
        ('finance.manager@company.com', 'hr.manager@company.com', 'Invoice Processed - Invoice_2024_001.pdf', 
         '<html><body><h2>Document Review Complete</h2><p>Your invoice Invoice_2024_001.pdf has been processed and approved.</p></body></html>',
         None, 'Invoice_2024_001.pdf'),
        ('general.employee@company.com', 'finance@company.com', 'Expense Report Submitted - Expense_Report.pdf', 
         '<html><body><h2>New Expense Report</h2><p>Expense_Report.pdf submitted for processing.</p><p><strong>Priority:</strong> Low</p></body></html>',
         None, 'Expense_Report.pdf'),

        # Legal Department emails
        ('legal.manager@company.com', 'legal@company.com', 'High Priority Legal Document - Contract_ABC_Corp.pdf', 
         '<html><body><h2>High Priority Document Alert</h2><p>Contract_ABC_Corp.pdf requires immediate legal review.</p><p><strong>Priority:</strong> High</p></body></html>',
         None, 'Contract_ABC_Corp.pdf'),
        ('legal.manager@company.com', 'legal@company.com', 'Legal Compliance Document - Legal_Compliance.pdf', 
         '<html><body><h2>Compliance Review</h2><p>Legal_Compliance.pdf uploaded for compliance review.</p><p><strong>Priority:</strong> High</p></body></html>',
         None, 'Legal_Compliance.pdf'),

        # IT Department emails
        ('it.manager@company.com', 'it@company.com', 'IT Security Policy Update Required - IT_Security_Policy.docx', 
         '<html><body><h2>Security Policy Review</h2><p>IT_Security_Policy.docx uploaded for review and approval.</p><p><strong>Priority:</strong> High</p></body></html>',
         None, 'IT_Security_Policy.docx'),

        # Sales Department emails
        ('sales.manager@company.com', 'sales@company.com', 'Q4 Sales Report Available - Sales_Report_Q4.xlsx', 
         '<html><body><h2>Sales Report Ready</h2><p>Sales_Report_Q4.xlsx has been uploaded for review.</p><p><strong>Priority:</strong> Medium</p></body></html>',
         None, 'Sales_Report_Q4.xlsx'),

        # Marketing Department emails
        ('finance.manager@company.com', 'marketing@company.com', 'Marketing Campaign Document - Marketing_Campaign.pptx', 
         '<html><body><h2>New Marketing Document</h2><p>Marketing_Campaign.pptx uploaded for marketing team review.</p><p><strong>Priority:</strong> Medium</p></body></html>',
         None, 'Marketing_Campaign.pptx'),

        # System notifications
        ('noreply@idcr-system.com', 'general.employee@company.com', 'Welcome to IDCR System', 
         '<html><body><h2>Welcome to IDCR System!</h2><p>Your account has been successfully created. You can now upload and manage documents.</p></body></html>',
         None, None),
        ('noreply@idcr-system.com', 'hr.manager@company.com', 'Welcome to IDCR System - Manager Access', 
         '<html><body><h2>Welcome to IDCR System!</h2><p>Your manager account is now active. You can review documents and manage your department.</p></body></html>',
         None, None),
        ('noreply@idcr-system.com', 'finance.manager@company.com', 'Welcome to IDCR System - Manager Access', 
         '<html><body><h2>Welcome to IDCR System!</h2><p>Your manager account is now active. You can review documents and manage your department.</p></body></html>',
         None, None),
        ('noreply@idcr-system.com', 'legal.manager@company.com', 'Welcome to IDCR System - Manager Access', 
         '<html><body><h2>Welcome to IDCR System!</h2><p>Your manager account is now active. You can review documents and manage your department.</p></body></html>',
         None, None),
    ]

    for sent_by, received_by, subject, body, doc_id, file_name in sample_emails:
        email_id = str(uuid.uuid4())
        # Create emails from the past few days with more realistic timestamps
        sent_time = datetime.datetime.utcnow() - datetime.timedelta(days=random.randint(0, 14), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        cursor.execute('''
            INSERT OR IGNORE INTO email_notifications (email_id, sent_by, received_by, subject, body, doc_id, file_name, status, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (email_id, sent_by, received_by, subject, body, doc_id, file_name, 'sent', sent_time.isoformat()))

    conn.commit()
    conn.close()
    print("✓ Database initialized")


# Pydantic models
class UserRegistration(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    department: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    department: str
    role: str


class DocumentUpload(BaseModel):
    filename: str
    file_size: int
    file_type: str


class BulkUploadRequest(BaseModel):
    batch_name: str
    files: List[DocumentUpload]


class BulkUploadResponse(BaseModel):
    batch_id: str
    message: str
    total_files: int


class DocumentInfo(BaseModel):
    doc_id: str
    original_name: str
    file_size: int
    file_type: str
    uploaded_at: str
    processing_status: str
    document_type: Optional[str] = None
    department: Optional[str] = None
    priority: Optional[str] = None
    classification_confidence: Optional[float] = None
    page_count: Optional[int] = None
    tags: Optional[List[str]] = None
    review_status: Optional[str] = None
    reviewed_by: Optional[str] = None


class DocumentReview(BaseModel):
    doc_id: str
    status: str  # approved, rejected
    comments: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total_count: int
    page: int
    page_size: int


# Utility functions
def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == hashed


def create_access_token(data: dict):
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    try:
        payload = jwt.decode(credentials.credentials,
                             SECRET_KEY,
                             algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM users WHERE user_id = ? AND is_active = 1',
            (user_id, ))
        user = cursor.fetchone()
        conn.close()

        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        return {
            'user_id': user[0],
            'email': user[1],
            'full_name': user[3],
            'department': user[4],
            'role': user[5]
        }
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def send_email(to_email: str, subject: str, body: str, doc_id: str = None, file_name: str = None, sender_email: str = None):
    """Send email using Outlook SMTP with fallback - DEMO VERSION"""
    # Use provided sender email or default to system email
    from_email = sender_email or EMAIL_USER

    # For demo purposes, we'll log the email instead of actually sending it
    print(f"\n📧 EMAIL NOTIFICATION (DEMO MODE)")
    print(f"From: {from_email}")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print(f"Body Preview: {body[:200]}...")
    print(f"✅ Email logged successfully (not actually sent in demo)\n")

    # Track email in database
    email_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO email_notifications (email_id, sent_by, received_by, subject, body, doc_id, file_name, status, sent_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (email_id, from_email, to_email, subject, body, doc_id, file_name, 'sent', datetime.datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

    # Try to actually send email, but don't fail if it doesn't work
    try:
        # Create message with fallback approach
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()

        print(f"📧 Email actually sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"📧 Email sending failed (expected in demo): {str(e)}")
        print(f"📧 Continuing with demo mode - email notifications are logged above")
        return True  # Return True so the process continues


# Mount static files for the project
app.mount("/static",
          StaticFiles(directory="Final-project_training"),
          name="static")

# Mount uploads directory
app.mount("/uploads",
          StaticFiles(directory="uploads"),
          name="uploads")

@app.get("/")
async def serve_frontend():
    """Serve the main frontend application"""
    return FileResponse("Final-project_training/index.html")

@app.get("/index.html")
async def serve_index():
    """Alternative path to serve frontend"""
    return FileResponse("Final-project_training/index.html")

@app.get("/app")
async def serve_app():
    """Another path to serve frontend"""
    return FileResponse("Final-project_training/index.html")


@app.get("/favicon.ico")
async def favicon():
    return {"message": "No favicon"}


# Authentication endpoints
@app.post("/api/register")
async def register_user(user_data: UserRegistration):
    """Register a new user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if user already exists
    cursor.execute('SELECT user_id FROM users WHERE email = ?',
                   (user_data.email, ))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    user_id = str(uuid.uuid4())
    password_hash = hash_password(user_data.password)

    cursor.execute(
        '''
        INSERT INTO users (user_id, email, password_hash, full_name, department, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, user_data.email, password_hash, user_data.full_name,
          user_data.department or 'general', datetime.datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

    # Send welcome email
    welcome_body = f"""
    <html>
        <body>
            <h2>Welcome to IDCR System!</h2>
            <p>Dear {user_data.full_name},</p>
            <p>Your account has been successfully created. You can now upload and manage your documents.</p>
            <p>Best regards,<br>IDCR Team</p>
        </body>
    </html>
    """
    send_email(user_data.email, "Welcome to IDCR System", welcome_body, None, None, "noreply@idcr-system.com")

    return {"message": "User registered successfully", "user_id": user_id}


@app.post("/api/login")
async def login_user(user_data: UserLogin):
    """Login user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE email = ? AND is_active = 1',
                   (user_data.email, ))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(user_data.password, user[2]):
        raise HTTPException(status_code=401,
                            detail="Invalid email or password")

    access_token = create_access_token(data={"sub": user[0]})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user[0],
            "email": user[1],
            "full_name": user[3],
            "department": user[4],
            "role": user[5]
        }
    }


@app.get("/api/me")
async def get_current_user_info(
        current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@app.get("/health")
async def health_check():
    """Check if backend services are running"""
    services = {
        "api_gateway": "http://0.0.0.0:8000",
        "classification": "http://0.0.0.0:8001",
        "routing_engine": "http://0.0.0.0:8002",
        "content_analysis": "http://0.0.0.0:8003",
        "workflow_integration": "http://0.0.0.0:8004"
    }

    status = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for service, url in services.items():
            try:
                response = await client.get(f"{url}/ping")
                status[
                    service] = "healthy" if response.status_code == 200 else "unhealthy"
            except Exception as e:
                status[service] = f"offline: {str(e)}"

    return {"services": status}


# Microservice URLs - using existing microservices
CLASSIFICATION_SERVICE_URL = "http://0.0.0.0:8001"
ROUTING_ENGINE_URL = "http://0.0.0.0:8002"
CONTENT_ANALYSIS_URL = "http://0.0.0.0:8003"
WORKFLOW_INTEGRATION_URL = "http://0.0.0.0:8004"


@app.post("/api/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_documents(
        files: List[UploadFile] = File(...),
        batch_name: str = Form(...),
        current_user: dict = Depends(get_current_user)):
    """Handle bulk document upload (up to 20+ files)"""

    if len(files) > 50:
        raise HTTPException(
            status_code=400,
            detail="Too many files. Maximum 50 files per batch.")

    # Validate file types
    allowed_types = {
        'application/pdf', 'text/plain',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }

    # Validate files
    for file in files:
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=
                f"Unsupported file type: {file.content_type} for file {file.filename}"
            )

        # Check file size (10MB limit per file)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {file.filename} (Max 10MB per file)")
        # Reset file pointer
        await file.seek(0)

    batch_id = str(uuid.uuid4())
    upload_dir = f"uploads/{batch_id}"
    os.makedirs(upload_dir, exist_ok=True)

    # Create batch record
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        '''
        INSERT INTO upload_batches (batch_id, user_id, batch_name, total_files, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (batch_id, current_user['user_id'], batch_name, len(files),
          datetime.datetime.utcnow().isoformat()))

    saved_files = []

    # Save files and create document records
    for file in files:
        try:
            doc_id = str(uuid.uuid4())
            file_path = f"{upload_dir}/{file.filename}"

            # Save file to disk
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            # Create document record
            cursor.execute(
                '''
                INSERT INTO documents (
                    doc_id, user_id, original_name, file_path, file_size, file_type, 
                    mime_type, uploaded_at, processing_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
                (doc_id, current_user['user_id'], file.filename, file_path,
                 len(content), file.filename.split('.')[-1].lower(),
                 file.content_type, datetime.datetime.utcnow().isoformat(), 'uploaded'))

            saved_files.append({
                'doc_id': doc_id,
                'filename': file.filename,
                'size': len(content)
            })

        except Exception as e:
            print(f"Error saving file {file.filename}: {e}")
            continue

    conn.commit()
    conn.close()

    # Start background processing
    asyncio.create_task(
        process_batch_async(batch_id, saved_files, current_user))

    return BulkUploadResponse(
        batch_id=batch_id,
        message=f"Successfully uploaded {len(saved_files)} files",
        total_files=len(saved_files))


async def process_batch_async(batch_id: str, files: List[dict], user: dict):
    """Process uploaded files asynchronously"""
    processed = 0
    failed = 0

    for file_info in files:
        try:
            # Get document details
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM documents WHERE doc_id = ?',
                           (file_info['doc_id'], ))
            doc_row = cursor.fetchone()
            conn.close()

            if not doc_row:
                continue

            # Update status to processing
            update_document_status(file_info['doc_id'], 'processing')

            # Enhanced content extraction for all document types
            try:
                file_path = doc_row[3]
                content = ""
                mime_type = doc_row[6]
                filename = doc_row[2]

                if mime_type == 'application/pdf':
                    # Handle PDF files
                    try:
                        import PyPDF2
                        with open(file_path, 'rb') as pdf_file:
                            pdf_reader = PyPDF2.PdfReader(pdf_file)
                            text_content = []
                            for page in pdf_reader.pages[:5]:  # Limit to first 5 pages
                                text_content.append(page.extract_text())
                            content = '\n'.join(text_content)
                            if not content.strip():
                                content = f"PDF document: {filename} - Contains {len(pdf_reader.pages)} pages"
                    except Exception as pdf_error:
                        print(f"PDF reading error: {pdf_error}")
                        content = f"PDF document: {filename} - Unable to extract text content"

                elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                    # Handle DOCX files
                    try:
                        import docx
                        doc = docx.Document(file_path)
                        paragraphs = []
                        for para in doc.paragraphs[:50]:  # Limit to first 50 paragraphs
                            if para.text.strip():
                                paragraphs.append(para.text)
                        content = '\n'.join(paragraphs)
                        if not content.strip():
                            content = f"DOCX document: {filename} - Document structure detected but no readable text"
                    except Exception as docx_error:
                        print(f"DOCX reading error: {docx_error}")
                        content = f"DOCX document: {filename} - Unable to extract text content"

                elif mime_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                    # Handle Excel files
                    try:
                        import openpyxl
                        workbook = openpyxl.load_workbook(file_path)
                        sheet_data = []
                        for sheet_name in workbook.sheetnames[:3]:  # Limit to first 3 sheets
                            sheet = workbook[sheet_name]
                            for row in sheet.iter_rows(max_row=20, values_only=True):  # Limit to first 20 rows
                                row_text = ' '.join([str(cell) for cell in row if cell is not None])
                                if row_text.strip():
                                    sheet_data.append(row_text)
                        content = '\n'.join(sheet_data)
                        if not content.strip():
                            content = f"Excel spreadsheet: {filename} - Contains data in {len(workbook.sheetnames)} sheets"
                    except Exception as excel_error:
                        print(f"Excel reading error: {excel_error}")
                        content = f"Excel spreadsheet: {filename} - Unable to extract content"

                elif mime_type.startswith('text/'):
                    # Handle text files
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()[:10000]  # Limit to 10KB
                    except Exception as text_error:
                        print(f"Text file reading error: {text_error}")
                        content = f"Text file: {filename} - Unable to read content"

                elif mime_type.startswith('image/'):
                    # Handle image files with OCR potential
                    try:
                        # Try to use OCR if available (optional)
                        import pytesseract
                        from PIL import Image
                        image = Image.open(file_path)
                        ocr_text = pytesseract.image_to_string(image)
                        content = ocr_text if ocr_text.strip() else f"Image file: {filename} - Image processed, no readable text detected"
                    except ImportError:
                        content = f"Image file: {filename} - Image content detected, OCR not available"
                    except Exception as image_error:
                        print(f"Image processing error: {image_error}")
                        content = f"Image file: {filename} - Image format recognized"

                else:
                    # Other file types - try to read as text
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            potential_content = f.read()[:5000]  # Limit to 5KB
                            if potential_content.strip():
                                content = potential_content
                            else:
                                content = f"Binary file: {filename} - File type: {mime_type}"
                    except:
                        content = f"Binary file: {filename} - File type: {mime_type}"

            except Exception as e:
                print(f"File reading error: {e}")
                content = f"Error reading file: {filename} - {str(e)}"

            # Simple local classification (fallback if microservice not available)
            classification_result = classify_document_locally(content, doc_row[2])

            # Try to use microservice if available, otherwise use local classification
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    with open(doc_row[3], 'rb') as f:
                        files_payload = {"file": (doc_row[2], f, doc_row[6])}
                        response = await client.post(
                            CLASSIFICATION_SERVICE_URL + "/classify", 
                            files=files_payload
                        )

                        if response.status_code == 200:
                            classification_result = response.json()
            except Exception as e:
                print(f"Microservice unavailable, using local classification: {e}")

            # Update document with classification results
            update_document_classification(file_info['doc_id'], classification_result)
            update_document_status(file_info['doc_id'], 'classified')

            # Send notification to department
            await notify_department(file_info['doc_id'], classification_result, user)
            processed += 1

        except Exception as e:
            print(f"Error processing document {file_info['doc_id']}: {e}")
            update_document_status(file_info['doc_id'], 'failed')
            failed += 1

    # Update batch status
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''
        UPDATE upload_batches 
        SET processed_files = ?, failed_files = ?, completed_at = ?, status = ?
        WHERE batch_id = ?
    ''', (processed, failed, datetime.datetime.utcnow().isoformat(), 'completed',
          batch_id))
    conn.commit()
    conn.close()


def classify_document_locally(content: str, filename: str):
    """Local classification as fallback when microservice is unavailable"""
    # Handle large documents by limiting content length for processing
    content_to_analyze = content[:5000] if len(content) > 5000 else content
    content_lower = content_to_analyze.lower()
    filename_lower = filename.lower()

    # Enhanced file type detection
    file_extension = filename_lower.split('.')[-1] if '.' in filename_lower else ''

    # Define keywords for priority
    high_priority_keywords = ["EOD", "end of day", "today", "asap", "urgent", "immediate", "24 hours", "deadline today", "due today", "respond by", "reply immediately",
                              "action required", "requires immediate attention", "please review urgently", "critical issue", "resolve now",
                              "escalated", "service disruption", "breach", "incident", "system down", "customer complaint", "payment failed",
                              "today's meeting", "final review", "must attend", "confirmation needed"]
    medium_priority_keywords = ["reminder", "follow up", "this week", "pending", "awaiting response", "check status", "update needed",
                                "tomorrow", "due in 2 days", "schedule by", "before Friday", "complete by", "ETA",
                                "scheduled for", "calendar invite", "tentative", "planned discussion", "agenda",
                                "work in progress", "assigned", "need update", "submit by", "to be reviewed"]

    # Determine keyword-based priority
    keyword_priority = "low"  # Default
    if any(keyword in content_lower for keyword in high_priority_keywords):
        keyword_priority = "high"
    elif any(keyword in content_lower for keyword in medium_priority_keywords):
        keyword_priority = "medium"

    # Enhanced classification for all departments with improved keywords
    classification_rules = [
        # Finance & Accounting - High Priority
        {
            "keywords": ["invoice", "payment", "finance", "bill", "receipt", "accounting", "budget", "expense", "revenue", "profit", "loss", "tax", "audit", "financial statement", "balance sheet", "cash flow", "accounts payable", "accounts receivable", "payroll", "salary", "wage", "reimbursement", "cost", "expenditure", "vendor payment", "purchase order", "billing", "transaction", "refund", "deposit"],
            "filename_keywords": ["invoice", "finance", "bill", "receipt", "payment", "expense", "budget", "financial", "tax", "audit", "payroll", "cost", "po", "purchase", "billing", "transaction"],
            "doc_type": "receipt" if "receipt" in filename_lower or "receipt" in content_lower else "financial_document",
            "department": "finance",
            "confidence": 0.95,
            "base_priority": "high",
            "tags": ["finance", "accounting", "financial"]
        },
        # Legal - High Priority
        {
            "keywords": ["contract", "agreement", "legal", "terms", "compliance", "policy", "regulation", "lawsuit", "litigation", "intellectual property", "copyright", "trademark", "patent", "non-disclosure", "nda", "privacy policy", "terms of service", "liability", "warranty", "indemnification", "arbitration", "clause", "amendment", "addendum", "legal notice", "cease and desist"],
            "filename_keywords": ["contract", "legal", "agreement", "terms", "compliance", "policy", "nda", "lawsuit", "patent", "copyright", "trademark", "liability", "amendment"],
            "doc_type": "legal_document",
            "department": "legal",
            "confidence": 0.92,
            "base_priority": "high",
            "tags": ["legal", "contract", "compliance"]
        },
        # Human Resources - Medium Priority
        {
            "keywords": ["employee", "hr", "human resources", "personnel", "hiring", "training", "performance", "recruitment", "onboarding", "benefits", "leave", "vacation", "sick leave", "maternity", "paternity", "disciplinary", "termination", "resignation", "promotion", "performance review", "appraisal", "job description", "organizational chart", "employee handbook", "workplace policy", "harassment", "diversity", "inclusion"],
            "filename_keywords": ["hr", "employee", "personnel", "hiring", "training", "benefits", "leave", "performance", "recruitment", "onboarding", "handbook", "policy"],
            "doc_type": "hr_document",
            "department": "hr",
            "confidence": 0.88,
            "base_priority": "medium",
            "tags": ["hr", "employee", "personnel"]
        },
        # Sales - High Priority
        {
            "keywords": ["sales", "lead", "customer", "deal", "proposal", "quotation", "order", "client", "prospect", "opportunity", "pipeline", "crm", "revenue", "commission", "target", "forecast", "sales report", "customer acquisition", "retention", "upsell", "cross-sell", "conversion", "roi", "kpi", "territory", "account management"],
            "filename_keywords": ["sales", "lead", "proposal", "quote", "order", "client", "customer", "deal", "opportunity", "pipeline", "forecast", "commission"],
            "doc_type": "sales_document",
            "department": "sales",
            "confidence": 0.90,
            "base_priority": "high",
            "tags": ["sales", "customer", "revenue"]
        },
        # Marketing - Medium Priority  
        {
            "keywords": ["marketing", "campaign", "advertisement", "promotion", "brand", "social media", "digital marketing", "content marketing", "seo", "sem", "ppc", "email marketing", "influencer", "analytics", "metrics", "engagement", "reach", "impression", "conversion rate", "market research", "competitor analysis", "target audience", "demographic", "segmentation"],
            "filename_keywords": ["marketing", "campaign", "ad", "promo", "brand", "social", "seo", "analytics", "content", "digital", "email"],
            "doc_type": "marketing_document",
            "department": "marketing",
            "confidence": 0.85,
            "base_priority": "medium",
            "tags": ["marketing", "campaign", "brand"]
        },
        # IT - High Priority
        {
            "keywords": ["technology", "it", "software", "hardware", "system", "network", "security", "server", "database", "infrastructure", "cybersecurity", "firewall", "backup", "cloud", "api", "integration", "deployment", "maintenance", "troubleshooting", "bug report", "feature request", "technical documentation", "user manual", "system requirements"],
            "filename_keywords": ["it", "tech", "software", "system", "network", "security", "server", "database", "cloud", "api", "bug", "technical"],
            "doc_type": "it_document",
            "department": "it",
            "confidence": 0.88,
            "base_priority": "high",
            "tags": ["it", "technology", "technical"]
        },
        # Operations
        {
            "keywords": ["operations", "process", "workflow", "procedure", "logistics", "supply chain"],
            "filename_keywords": ["operations", "process", "workflow", "procedure"],
            "doc_type": "operations_document",
            "department": "operations",
            "confidence": 0.7,
            "base_priority": "medium",
            "tags": ["operations", "process"]
        },
        # Customer Support
        {
            "keywords": ["support", "ticket", "issue", "complaint", "feedback", "resolution"],
            "filename_keywords": ["support", "ticket", "issue"],
            "doc_type": "support_document",
            "department": "support",
            "confidence": 0.7,
            "base_priority": "medium",
            "tags": ["support", "customer"]
        },
        # Procurement
        {
            "keywords": ["procurement", "purchase", "vendor", "supplier", "acquisition", "RFP"],
            "filename_keywords": ["procurement", "purchase", "vendor", "supplier"],
            "doc_type": "procurement_document",
            "department": "procurement",
            "confidence": 0.75,
            "base_priority": "medium",
            "tags": ["procurement", "purchase"]
        },
        # Product / R&D
        {
            "keywords": ["product", "research", "development", "innovation", "design", "prototype"],
            "filename_keywords": ["product", "research", "development", "design"],
            "doc_type": "product_document",
            "department": "product",
            "confidence": 0.75,
            "base_priority": "medium",
            "tags": ["product", "research"]
        },
        # Administration
        {
            "keywords": ["administration", "admin", "office", "facility", "maintenance", "general"],
            "filename_keywords": ["admin", "office", "facility", "maintenance"],
            "doc_type": "admin_document",
            "department": "administration",
            "confidence": 0.6,
            "base_priority": "low",
            "tags": ["administration", "office"]
        },
        # Executive / Management
        {
            "keywords": ["executive", "management", "board", "strategy", "decision", "leadership"],
            "filename_keywords": ["executive", "management", "board", "strategy"],
            "doc_type": "executive_document",
            "department": "executive",
            "confidence": 0.8,
            "base_priority": "high",
            "tags": ["executive", "management"]
        }
    ]

    # Check each classification rule
    for rule in classification_rules:
        content_match = any(word in content_lower for word in rule["keywords"])
        filename_match = any(word in filename_lower for word in rule["filename_keywords"])

        if content_match or filename_match:
            # Priority determination: keyword-based priority takes precedence
            final_priority = keyword_priority
            # If keyword priority is medium and base priority is high/low, adjust accordingly
            if keyword_priority == "medium":
                final_priority = rule["base_priority"]

            return {
                "doc_type": rule["doc_type"],
                "department": rule["department"],
                "confidence": rule["confidence"],
                "priority": final_priority,
                "extracted_text": content[:1000],  # Increased content length
                "page_count": 1,
                "language": "en",
                "tags": rule["tags"]
            }

    # Default classification
    return {
        "doc_type": "general_document",
        "department": "general",
        "confidence": 0.5,
        "priority": "low",
        "extracted_text": content[:1000],
        "page_count": 1,
        "language": "en",
        "tags": ["general"]
    }


async def notify_department(doc_id: str, classification_result: dict,
                            user: dict):
    """Send notification to department about new document"""
    department = classification_result.get('department', 'general')
    doc_type = classification_result.get('doc_type', 'document')

    # Get department email and document details
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT dept_email, manager_email FROM departments WHERE dept_id = ?',
                   (department, ))
    dept_result = cursor.fetchone()

    cursor.execute('SELECT original_name FROM documents WHERE doc_id = ?', (doc_id,))
    doc_result = cursor.fetchone()
    file_name = doc_result[0] if doc_result else "Unknown"
    conn.close()

    if dept_result:
        dept_email = dept_result[0]
        manager_email = dept_result[1]

        # Create descriptive subject based on document type
        doc_type_display = doc_type.replace('_', ' ').title()
        if doc_type == 'receipt':
            subject = f"New Receipt Uploaded by {user['full_name']} - {file_name}"
        else:
            subject = f"New {doc_type_display} Uploaded - {file_name}"

        body = f"""
        <html>
            <body>
                <h2>📄 New Document Uploaded for Review</h2>
                <p><strong>📋 Document:</strong> {file_name}</p>
                <p><strong>👤 Uploaded by:</strong> {user['full_name']} ({user['email']})</p>
                <p><strong>📂 Document Type:</strong> {doc_type_display}</p>
                <p><strong>🏢 Department:</strong> {department.title()}</p>
                <p><strong>⚡ Priority:</strong> {classification_result.get('priority', 'Medium').title()}</p>
                <p><strong>🎯 Confidence:</strong> {classification_result.get('confidence', 0):.1%}</p>
                <p><strong>🆔 Document ID:</strong> {doc_id}</p>
                <hr style="margin: 20px 0;">
                <p>Please log into the IDCR system to review this document.</p>
                <p><em>This notification was sent to the {department.title()} department.</em></p>
                <p>Best regards,<br>IDCR System</p>
            </body>
        </html>
        """

        # Send notification to both department email and manager email
        send_email(dept_email, subject, body, doc_id, file_name, user['email'])
        if manager_email and manager_email != dept_email:
            send_email(manager_email, subject, body, doc_id, file_name, user['email'])


def update_document_status(doc_id: str, status: str):
    """Update document processing status"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE documents SET processing_status = ? WHERE doc_id = ?',
        (status, doc_id))
    conn.commit()
    conn.close()


def update_document_classification(doc_id: str, classification_result: dict):
    """Update document with classification results"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tags_json = json.dumps(classification_result.get('tags', []))

    cursor.execute(
        '''
        UPDATE documents SET 
            extracted_text = ?, document_type = ?, department = ?, 
            priority = ?, classification_confidence = ?, page_count = ?,
            language = ?, tags = ?
        WHERE doc_id = ?
    ''', (classification_result.get(
            'extracted_text', ''), classification_result.get(
                'doc_type', ''), classification_result.get('department', ''),
          classification_result.get(
              'priority', ''), classification_result.get('confidence', 0.0),
          classification_result.get('page_count', 1),
          classification_result.get('language', 'en'), tags_json, doc_id))

    conn.commit()
    conn.close()


@app.post("/api/documents/{doc_id}/review")
async def review_document(doc_id: str,
                          review: DocumentReview,
                          current_user: dict = Depends(get_current_user)):
    """Review a document (approve/reject)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get document info
    cursor.execute(
        'SELECT user_id, original_name FROM documents WHERE doc_id = ?',
        (doc_id, ))
    doc_result = cursor.fetchone()

    if not doc_result:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")

    # Update document review status
    cursor.execute(
        '''
        UPDATE documents 
        SET review_status = ?, reviewed_by = ?, review_comments = ?, reviewed_at = ?
        WHERE doc_id = ?
    ''', (review.status, current_user['email'], review.comments,
          datetime.datetime.utcnow().isoformat(), doc_id))

    # Get user email who uploaded the document
    cursor.execute('SELECT email, full_name FROM users WHERE user_id = ?',
                   (doc_result[0], ))
    user_result = cursor.fetchone()

    conn.commit()
    conn.close()

    if user_result:
        user_email, user_name = user_result

        # Send notification email to user
        status_text = "approved" if review.status == "approved" else "rejected"
        subject = f"Document Review Complete - {status_text.title()}"

        body = f"""
        <html>
            <body>
                <h2>Document Review Complete</h2>
                <p>Dear {user_name},</p>
                <p>Your document <strong>{doc_result[1]}</strong> has been <strong>{status_text}</strong>.</p>
                <p><strong>Reviewed by:</strong> {current_user['full_name']} ({current_user['email']})</p>
                {f"<p><strong>Comments:</strong> {review.comments}</p>" if review.comments else ""}
                <p>You can view the details in your IDCR dashboard.</p>
                <p>Best regards,<br>IDCR Team</p>
            </body>
        </html>
        """

        send_email(user_email, subject, body, doc_id, doc_result[1], current_user['email'])

    return {"message": f"Document {review.status} successfully"}


@app.get("/api/documents", response_model=DocumentListResponse)
async def get_documents(page: int = 1,
                        page_size: int = 20,
                        status: str = None,
                        doc_type: str = None,
                        department: str = None,
                        search: str = None,
                        current_user: dict = Depends(get_current_user)):
    """Get paginated list of documents with filtering"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Build query with filters
    where_clauses = []
    params = []

    # If user is not admin, only show their documents or documents in their department
    if current_user['role'] != 'admin':
        if current_user['role'] == 'employee':
            where_clauses.append("user_id = ?")
            params.append(current_user['user_id'])
        else:  # department manager
            where_clauses.append("(user_id = ? OR department = ?)")
            params.extend(
                [current_user['user_id'], current_user['department']])

    if status:
        where_clauses.append("processing_status = ?")
        params.append(status)

    if doc_type:
        where_clauses.append("document_type = ?")
        params.append(doc_type)

    if department:
        where_clauses.append("department = ?")
        params.append(department)

    if search:
        where_clauses.append("(original_name LIKE ? OR extracted_text LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Get total count
    count_query = f"SELECT COUNT(*) FROM documents {where_sql}"
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]

    # Calculate offset for pagination
    offset = (page - 1) * page_size

    # Update query to include extracted_text
    query = f'''
        SELECT doc_id, original_name, file_size, file_type, uploaded_at, 
               processing_status, document_type, department, priority, 
               classification_confidence, page_count, tags, review_status, reviewed_by,
               extracted_text
        FROM documents {where_sql}
        ORDER BY uploaded_at DESC
        LIMIT ? OFFSET ?
    '''
    params.extend([page_size, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    documents = []
    for row in rows:
        tags = json.loads(row[11]) if row[11] else []
        doc = {
            "doc_id": row[0],
            "original_name": row[1],
            "file_size": row[2],
            "file_type": row[3],
            "uploaded_at": row[4],
            "processing_status": row[5],
            "document_type": row[6] or "",
            "department": row[7] or "",
            "priority": row[8] or "",
            "classification_confidence": row[9] or 0.0,
            "page_count": row[10] or 0,
            "tags": tags,
            "review_status": row[12] or "",
            "reviewed_by": row[13] or "",
            "extracted_text": row[14] or ""
        }
        documents.append(doc)

    return DocumentListResponse(documents=documents,
                                total_count=total_count,
                                page=page,
                                page_size=page_size)


@app.get("/api/documents/review")
async def get_review_documents(page: int = 1,
                              page_size: int = 50,
                              search: str = None,
                              review_status: str = None,
                              current_user: dict = Depends(get_current_user)):
    """Get documents for review based on user's department"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Build query with filters for review
    where_clauses = []
    params = []

    # Show documents based on user role and department
    if current_user['role'] == 'admin':
        # Admin can see all documents
        pass
    elif current_user['role'] == 'manager':
        # Managers can see ALL documents routed to their department, regardless of who uploaded them
        where_clauses.append("d.department = ?")
        params.append(current_user['department'])
    else:
        # Regular employees can only see their own documents
        where_clauses.append("d.user_id = ?")
        params.append(current_user['user_id'])

    if review_status:
        where_clauses.append("d.review_status = ?")
        params.append(review_status)

    if search:
        where_clauses.append("(d.original_name LIKE ? OR d.extracted_text LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Get documents with user information
    query = f'''
        SELECT d.doc_id, d.original_name, d.file_size, d.file_type, d.uploaded_at, 
               d.processing_status, d.document_type, d.department, d.priority, 
               d.classification_confidence, d.page_count, d.tags, d.review_status, 
               d.reviewed_by, d.user_id, u.full_name as uploaded_by_name, u.email as uploaded_by_email,
               d.extracted_text
        FROM documents d
        LEFT JOIN users u ON d.user_id = u.user_id
        {where_sql}
        ORDER BY d.uploaded_at DESC
        LIMIT ? OFFSET ?
    '''

    offset = (page - 1) * page_size
    params.extend([page_size, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Get total count
    count_query = f'''
        SELECT COUNT(*) 
        FROM documents d
        LEFT JOIN users u ON d.user_id = u.user_id
        {where_sql}
    '''
    cursor.execute(count_query, params[:-2])  # Remove limit and offset params
    total_count = cursor.fetchone()[0]

    conn.close()

    documents = []
    for row in rows:
        tags = json.loads(row[11]) if row[11] else []
        doc = {
            "doc_id": row[0],
            "original_name": row[1],
            "file_size": row[2],
            "file_type": row[3],
            "uploaded_at": row[4],
            "processing_status": row[5],
            "document_type": row[6] or "",
            "department": row[7] or "",
            "priority": row[8] or "",
            "classification_confidence": row[9] or 0.0,
            "page_count": row[10] or 0,
            "tags": tags,
            "review_status": row[12] or "pending",
            "reviewed_by": row[13] or "",
            "user_id": row[14],
            "uploaded_by": row[15] or "Unknown",
            "uploaded_by_email": row[16] or "",
            "extracted_text": row[17] or ""
        }
        documents.append(doc)

    return {
        "documents": documents,
        "total_count": total_count,
        "page": page,
        "page_size": page_size
    }


@app.get("/api/documents/{doc_id}")
async def get_document_details(doc_id: str,
                               current_user: dict = Depends(get_current_user)):
    """Get detailed information about a specific document"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM documents WHERE doc_id = ?', (doc_id, ))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check permissions
    if current_user['role'] == 'employee' and row[1] != current_user['user_id']:
        raise HTTPException(status_code=403, detail="Access denied")

    # Convert row to dictionary
    columns = [
        'doc_id', 'user_id', 'original_name', 'file_path', 'file_size',
        'file_type', 'mime_type', 'uploaded_at', 'processing_status',
        'extracted_text', 'ocr_confidence', 'document_type', 'department',
        'priority', 'classification_confidence', 'page_count', 'language',
        'tags', 'assigned_to', 'reviewed_by', 'review_status',
        'review_comments', 'reviewed_at'
    ]

    doc_dict = dict(zip(columns, row))
    if doc_dict['tags']:
        doc_dict['tags'] = json.loads(doc_dict['tags'])

    # If extracted_text is empty, try to read the file content
    if not doc_dict['extracted_text'] and doc_dict['file_path']:
        try:
            file_path = doc_dict['file_path']
            if os.path.exists(file_path):
                # Try to read file content based on file type
                if doc_dict['file_type'].lower() in ['txt', 'text']:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        doc_dict['extracted_text'] = content[:2000]  # Limit to 2000 chars
                elif doc_dict['mime_type'] == 'application/pdf':
                    # For PDF files, show a preview message
                    doc_dict['extracted_text'] = "[PDF File] - Content extraction not available in preview. File contains PDF document."
                elif doc_dict['mime_type'].startswith('image/'):
                    # For image files
                    doc_dict['extracted_text'] = f"[Image File] - {doc_dict['original_name']} - Image content not displayable in text format."
                else:
                    # For other file types
                    doc_dict['extracted_text'] = f"[{doc_dict['file_type'].upper()} File] - Content preview not available for this file type."
        except Exception as e:
            doc_dict['extracted_text'] = f"[Error] - Could not read file content: {str(e)}"

    return doc_dict


@app.get("/api/email-notifications")
async def get_email_notifications(page: int = 1, 
                                  page_size: int = 20,
                                  current_user: dict = Depends(get_current_user)):
    """Get email notifications for the current user with department-specific filtering"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get department email for current user
    cursor.execute('SELECT dept_email, manager_email FROM departments WHERE dept_id = ?', (current_user['department'],))
    dept_result = cursor.fetchone()
    user_dept_email = dept_result[0] if dept_result else f"{current_user['department']}@company.com"
    user_manager_email = dept_result[1] if dept_result else f"{current_user['department']}.manager@company.com"

    # Get emails based on user role with proper filtering
    offset = (page - 1) * page_size

    if current_user['role'] == 'admin':
        # Admins see all email notifications
        query = '''
            SELECT e.email_id, e.sent_by, e.received_by, e.subject, e.body, e.doc_id, 
                   e.file_name, e.status, e.sent_at, e.read_at,
                   d.original_name, d.document_type, d.priority, d.department,
                   u.full_name as sender_name, u2.full_name as recipient_name
            FROM email_notifications e
            LEFT JOIN documents d ON e.doc_id = d.doc_id
            LEFT JOIN users u ON e.sent_by = u.email
            LEFT JOIN users u2 ON e.received_by = u2.email
            ORDER BY e.sent_at DESC
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query, [page_size, offset])

    elif current_user['role'] == 'employee':
        # Employees see emails related to them or their uploaded documents
        query = '''
            SELECT e.email_id, e.sent_by, e.received_by, e.subject, e.body, e.doc_id, 
                   e.file_name, e.status, e.sent_at, e.read_at,
                   d.original_name, d.document_type, d.priority, d.department,
                   u.full_name as sender_name, u2.full_name as recipient_name
            FROM email_notifications e
            LEFT JOIN documents d ON e.doc_id = d.doc_id
            LEFT JOIN users u ON e.sent_by = u.email
            LEFT JOIN users u2 ON e.received_by = u2.email
            WHERE e.sent_by = ? OR e.received_by = ? OR d.user_id = ?
            ORDER BY e.sent_at DESC
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query, [current_user['email'], current_user['email'], current_user['user_id'], page_size, offset])

    else:  # managers
        # Managers see ALL emails related to their department including documents routed to their department
        query = '''
            SELECT e.email_id, e.sent_by, e.received_by, e.subject, e.body, e.doc_id, 
                   e.file_name, e.status, e.sent_at, e.read_at,
                   d.original_name, d.document_type, d.priority, d.department,
                   u.full_name as sender_name, u2.full_name as recipient_name
            FROM email_notifications e
            LEFT JOIN documents d ON e.doc_id = d.doc_id
            LEFT JOIN users u ON e.sent_by = u.email
            LEFT JOIN users u2 ON e.received_by = u2.email
            WHERE (e.sent_by = ? OR e.received_by = ? OR e.received_by = ? OR e.received_by = ? OR d.department = ?)
            ORDER BY e.sent_at DESC
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query, [current_user['email'], current_user['email'], user_dept_email, user_manager_email, current_user['department'], page_size, offset])

    emails = cursor.fetchall()

    # Get total count with same filtering logic
    if current_user['role'] == 'admin':
        cursor.execute('SELECT COUNT(*) FROM email_notifications')
        total_count_result = cursor.fetchone()
    elif current_user['role'] == 'employee':
        cursor.execute('''
            SELECT COUNT(*) FROM email_notifications e
            LEFT JOIN documents d ON e.doc_id = d.doc_id
            WHERE e.sent_by = ? OR e.received_by = ? OR d.user_id = ?
        ''', [current_user['email'], current_user['email'], current_user['user_id']])
        total_count_result = cursor.fetchone()
    else:  # managers
        cursor.execute('''
            SELECT COUNT(*) FROM email_notifications e
            LEFT JOIN documents d ON e.doc_id = d.doc_id
            WHERE (e.sent_by = ? OR e.received_by = ? OR e.received_by = ? OR e.received_by = ? OR d.department = ?)
        ''', [current_user['email'], current_user['email'], user_dept_email, user_manager_email, current_user['department']])
        total_count_result = cursor.fetchone()

    total_count = total_count_result[0] if total_count_result else 0

    conn.close()

    email_list = []
    for email in emails:
        # Determine if email was sent or received by current user or department
        email_type = "sent" if email[1] == current_user['email'] else "received"

        email_list.append({
            "email_id": email[0],
            "sent_by": email[1],
            "sent_by_name": email[14] if email[14] else ("IDCR System" if "noreply" in email[1] else email[1].split('@')[0].title()),
            "received_by": email[2],
            "received_by_name": email[15] if email[15] else email[2].split('@')[0].title(),
            "subject": email[3],
            "body_preview": email[4][:200] + "..." if email[4] and len(email[4]) > 200 else email[4],
            "doc_id": email[5],
            "file_name": email[6] or "N/A",
            "document_name": email[10] or email[6] or "N/A",
            "document_type": email[11] or "System Notification",
            "priority": email[12] or "Medium",
            "department": email[13] or current_user['department'].title(),
            "status": email[7],
            "sent_at": email[8],
            "read_at": email[9],
            "email_type": email_type
        })

    return {
        "emails": email_list,
        "total_count": total_count,
        "page": page,
        "page_size": page_size
    }

@app.get("/api/stats")
async def get_statistics(current_user: dict = Depends(get_current_user)):
    """Get document processing statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Build base query based on user role and department
        base_where = ""
        params = []

        if current_user['role'] == 'employee':
            # Employees see only their own documents
            base_where = "WHERE user_id = ?"
            params.append(current_user['user_id'])
        elif current_user['role'] == 'manager':
            # Managers see only documents from their department
            base_where = "WHERE department = ?"
            params.append(current_user['department'])
        elif current_user['role'] == 'admin':
            # Only admins see all documents
            base_where = ""
            params = []

        # Overall stats
        if base_where:
            cursor.execute(f'SELECT COUNT(*) FROM documents {base_where}', params)
            total_docs = cursor.fetchone()[0]

            cursor.execute(f'SELECT COUNT(*) FROM documents {base_where} AND processing_status = ?', params + ["classified"])
            processed_docs = cursor.fetchone()[0]

            cursor.execute(f'SELECT COUNT(*) FROM documents {base_where} AND processing_status = ?', params + ["processing"])
            pending_docs = cursor.fetchone()[0]

            cursor.execute(f'SELECT COUNT(*) FROM documents {base_where} AND processing_status = ?', params + ["failed"])
            error_docs = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT COUNT(*) FROM documents')
            total_docs = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM documents WHERE processing_status = ?', ["classified"])
            processed_docs = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM documents WHERE processing_status = ?', ["processing"])
            pending_docs = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM documents WHERE processing_status = ?', ["failed"])
            error_docs = cursor.fetchone()[0]

        # Document type breakdown
        if base_where:
            cursor.execute(
                f'''
                SELECT document_type, COUNT(*) 
                FROM documents 
                {base_where} AND document_type IS NOT NULL 
                GROUP BY document_type
            ''', params)
        else:
            cursor.execute(
                '''
                SELECT document_type, COUNT(*) 
                FROM documents 
                WHERE document_type IS NOT NULL 
                GROUP BY document_type
            ''')
        doc_types = dict(cursor.fetchall())

        # Department breakdown
        if base_where:
            cursor.execute(
                f'''
                SELECT department, COUNT(*) 
                FROM documents 
                {base_where} AND department IS NOT NULL 
                GROUP BY department
            ''', params)
        else:
            cursor.execute(
                '''
                SELECT department, COUNT(*) 
                FROM documents 
                WHERE department IS NOT NULL 
                GROUP BY department
            ''')
        departments = dict(cursor.fetchall())

        # Priority breakdown
        if base_where:
            cursor.execute(
                f'''
                SELECT priority, COUNT(*) 
                FROM documents 
                {base_where} AND priority IS NOT NULL 
                GROUP BY priority
            ''', params)
        else:
            cursor.execute(
                '''
                SELECT priority, COUNT(*) 
                FROM documents 
                WHERE priority IS NOT NULL 
                GROUP BY priority
            ''')
        priorities = dict(cursor.fetchall())

        # Monthly upload trends (last 6 months)
        if base_where:
            cursor.execute(
                f'''
                SELECT DATE(uploaded_at) as upload_date, COUNT(*) 
                FROM documents 
                {base_where} AND uploaded_at >= date('now', '-6 months')
                GROUP BY DATE(uploaded_at)
                ORDER BY upload_date
            ''', params)
        else:
            cursor.execute(
                '''
                SELECT DATE(uploaded_at) as upload_date, COUNT(*) 
                FROM documents 
                WHERE uploaded_at >= date('now', '-6 months')
                GROUP BY DATE(uploaded_at)
                ORDER BY upload_date
            ''')
        daily_uploads = cursor.fetchall()

        return {
            "total_documents": total_docs,
            "processed_documents": processed_docs,
            "pending_documents": pending_docs,
            "error_documents": error_docs,
            "document_types": doc_types,
            "departments": departments,
            "priorities": priorities,
            "upload_trends": [{"date": row[0], "count": row[1]} for row in daily_uploads],
            "processing_rate": round((processed_docs / total_docs * 100) if total_docs > 0 else 0, 2)
        }

    except Exception as e:
        print(f"Error in statistics endpoint: {e}")
        # Return default empty statistics in case of error
        return {
            "total_documents": 0,
            "processed_documents": 0,
            "pending_documents": 0,
            "error_documents": 0,
            "document_types": {},
            "departments": {},
            "priorities": {},
            "upload_trends": [],
            "processing_rate": 0
        }

    finally:
        # Ensure connection is always closed
        conn.close()


# Main startup
if __name__ == "__main__":
    print("🚀 Starting IDCR Demo Server...")
    print("📂 Frontend available at: http://0.0.0.0:5000")
    print("📊 API docs available at: http://0.0.0.0:5000/docs")
    uvicorn.run(app, host="0.0.0.0", port=5000)