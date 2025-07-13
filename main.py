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
    target_department: Optional[str] = None # Added target_department


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
    except jwt.PyJWTError as e:
        print(f"JWT validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


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
async def bulk_upload(
    files: List[UploadFile] = File(...),
    batch_name: str = Form(...),
    target_department: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload multiple documents for classification and routing"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if not target_department:
        raise HTTPException(status_code=400, detail="Target department is required")

    batch_id = str(uuid.uuid4())
    uploaded_files = []
    failed_files = []

    # Create batch record
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO upload_batches (batch_id, user_id, batch_name, total_files, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (batch_id, current_user['user_id'], batch_name, len(files), datetime.datetime.utcnow().isoformat()))

    # Create uploads directory if it doesn't exist
    upload_dir = Path("uploads") / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        try:
            # Validate file
            if file.size > 10 * 1024 * 1024:  # 10MB limit
                failed_files.append(f"{file.filename}: File too large")
                continue

            # Save file
            file_path = upload_dir / secure_filename(file.filename)
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # Extract text content
            extracted_text = ""
            try:
                if file.filename.lower().endswith('.pdf'):
                    with open(file_path, 'rb') as pdf_file:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        for page in pdf_reader.pages:
                            extracted_text += page.extract_text()
                elif file.filename.lower().endswith('.txt'):
                    with open(file_path, 'r', encoding='utf-8') as txt_file:
                        extracted_text = txt_file.read()
                elif file.filename.lower().endswith('.docx'):
                    doc = docx.Document(file_path)
                    extracted_text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            except Exception as e:
                print(f"Text extraction failed for {file.filename}: {e}")
                extracted_text = f"Text extraction failed: {str(e)}"

            # Simulate classification
            doc_type = "general_document"
            priority = "medium"
            if "invoice" in file.filename.lower() or "receipt" in file.filename.lower():
                doc_type = "financial_document"
                priority = "high"
            elif "contract" in file.filename.lower() or "legal" in file.filename.lower():
                doc_type = "legal_document"
                priority = "high"
            elif "hr" in file.filename.lower() or "employee" in file.filename.lower():
                doc_type = "hr_document"
                priority = "medium"

            # Create document record
            doc_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO documents (
                    doc_id, user_id, original_name, file_path, file_size, file_type, 
                    mime_type, uploaded_at, processing_status, extracted_text, 
                    document_type, department, priority, classification_confidence,
                    page_count, language, tags, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                doc_id, current_user['user_id'], file.filename, str(file_path), 
                file.size, file.filename.split('.')[-1].lower(),
                file.content_type or 'application/octet-stream',
                datetime.datetime.utcnow().isoformat(), "classified", extracted_text,
                doc_type, target_department, priority, 0.85, 1, 'en',
                f'["{doc_type}", "{target_department}"]', "pending"
            ))

            uploaded_files.append({
                'doc_id': doc_id,
                'filename': file.filename,
                'department': target_department,
                'type': doc_type,
                'priority': priority
            })

        except Exception as e:
            failed_files.append(f"{file.filename}: {str(e)}")

    # Update batch status
    cursor.execute('''
        UPDATE upload_batches 
        SET processed_files = ?, failed_files = ?, status = ?, completed_at = ?
        WHERE batch_id = ?
    ''', (len(uploaded_files), len(failed_files), 'completed', 
          datetime.datetime.utcnow().isoformat(), batch_id))

    conn.commit()
    conn.close()

    # Send notifications to department managers
    if uploaded_files:
        # Get department manager emails
        dept_manager_emails = {
            'hr': 'hr.manager@company.com',
            'finance': 'finance.manager@company.com',
            'legal': 'legal.manager@company.com',
            'sales': 'sales.manager@company.com',
            'marketing': 'marketing.manager@company.com',
            'it': 'it.manager@company.com',
            'operations': 'operations.manager@company.com',
            'support': 'support.manager@company.com',
            'procurement': 'procurement.manager@company.com',
            'product': 'product.manager@company.com',
            'administration': 'administration.manager@company.com',
            'executive': 'executive.manager@company.com'
        }

        manager_email = dept_manager_emails.get(target_department, 'admin@company.com')
        
        # Send notification email to department manager
        subject = f"New Documents Uploaded to {target_department.upper()} Department"
        body = f"""
        <html>
            <body>
                <h2>New Documents Uploaded for Review</h2>
                <p>Dear Department Manager,</p>
                <p>{current_user['full_name']} has uploaded {len(uploaded_files)} document(s) to the {target_department.upper()} department.</p>
                
                <h3>Documents:</h3>
                <ul>
        """
        
        for doc in uploaded_files:
            body += f"""
                    <li>
                        <strong>{doc['filename']}</strong><br>
                        Type: {doc['type']}<br>
                        Priority: {doc['priority']}<br>
                        Department: {doc['department'].upper()}
                    </li>
            """
        
        body += """
                </ul>
                <p>Please review these documents in the IDCR system.</p>
                <p>Best regards,<br>IDCR System</p>
            </body>
        </html>
        """

        send_email(manager_email, subject, body, None, None, current_user['email'])

        # Send confirmation email to uploader
        confirmation_subject = f"Document Upload Confirmation - {len(uploaded_files)} files processed"
        confirmation_body = f"""
        <html>
            <body>
                <h2>Upload Successful</h2>
                <p>Dear {current_user['full_name']},</p>
                <p>Your {len(uploaded_files)} document(s) have been successfully uploaded and sent to the {target_department.upper()} department for review.</p>
                <p>You will receive another notification once the documents are reviewed.</p>
                <p>Best regards,<br>IDCR System</p>
            </body>
        </html>
        """
        
        send_email(current_user['email'], confirmation_subject, confirmation_body, None, None, "noreply@idcr-system.com")

    return {
        "batch_id": batch_id,
        "message": f"Successfully uploaded {len(uploaded_files)} files to {target_department} department",
        "total_files": len(uploaded_files),
        "failed_files": failed_files if failed_files else None
    }