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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
import PyPDF2
import docx
from werkzeug.utils import secure_filename
import mimetypes
import tempfile
try:
    import pandas as pd
except ImportError:
    pd = None
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, EmailStr
import httpx
from datetime import timedelta
import re
import random

app = FastAPI(title="IDCR Enhanced Demo Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": exc.errors()}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled exception: {exc}")
    import traceback
    print(f"Full traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
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
    """Initialize the database with required tables"""
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

    # Email to name mapping for uploaded_by field
    email_to_name = {email: name for email, name, _, _, _ in demo_users}

    # Create documents table first (moved up before any inserts)
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
            uploaded_by TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Check if uploaded_by column exists in documents table, add if missing
    cursor.execute("PRAGMA table_info(documents)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'uploaded_by' not in columns:
        cursor.execute(
            'ALTER TABLE documents ADD COLUMN uploaded_by TEXT DEFAULT "General Employee"')

    # Add new columns if they don't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE documents ADD COLUMN reviewed_by TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute('ALTER TABLE documents ADD COLUMN review_date TIMESTAMP')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute('ALTER TABLE documents ADD COLUMN review_comments TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create sample documents for better statistics

    # Create sample priority documents first
    sample_priority_docs = [
        ('urgent_invoice.txt', 'hr.manager@company.com', 'finance', 'financial_document', 'high', 'classified', "urgent invoice payment"),
        ('reminder_contract.txt', 'hr.manager@company.com', 'legal', 'legal_document', 'medium', 'classified', "reminder contract terms"),
        ('fyi_report.txt', 'general.employee@company.com', 'general', 'general_document', 'low', 'classified', "fyi report summary"),
        ('hr_urgent_policy.txt', 'hr.manager@company.com', 'hr', 'hr_document', 'high', 'classified', "hr urgent policy update"),
        ('it_security_doc.txt', 'it.manager@company.com', 'it', 'it_document', 'high', 'classified', "it security policy"),
        ('sales_proposal.txt', 'sales.manager@company.com', 'sales', 'sales_document', 'medium', 'classified', "sales proposal document"),
        ('marketing_campaign.txt', 'finance.manager@company.com', 'marketing', 'marketing_document', 'low', 'classified', "marketing campaign plan"),
        ('operations_manual.txt', 'hr.manager@company.com', 'operations', 'operations_document', 'medium', 'classified', "operations manual"),
        ('support_ticket.txt', 'general.employee@company.com', 'support', 'support_document', 'high', 'classified', "customer support ticket"),
        ('procurement_order.txt', 'finance.manager@company.com', 'procurement', 'procurement_document', 'medium', 'classified', "procurement purchase order")
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

        # Get readable name for uploaded_by
        uploaded_by_name = email_to_name.get(user_email, 'General Employee')

        # Create sample document records
        cursor.execute('''
            INSERT OR IGNORE INTO documents (
                doc_id, user_id, original_name, file_path, file_size, file_type, 
                mime_type, uploaded_at, processing_status, document_type, department, 
                priority, classification_confidence, page_count, language, tags, 
                review_status, extracted_text, uploaded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_id, user_id, original_name, file_path, file_size, file_type,
            mime_type, datetime.datetime.utcnow().isoformat(), status, doc_type, dept,
            priority, 0.85, 1, 'en', '["' + doc_type + '", "' + dept + '"]',
            'approved' if status == 'approved' else 'pending', content, uploaded_by_name
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
        # Find user_id for the email
        cursor.execute("SELECT user_id FROM users WHERE email = ?", (user_email,))
        user_row = cursor.fetchone()
        user_id = user_row[0] if user_row else None

        # Get readable name for uploaded_by
        uploaded_by_name = email_to_name.get(user_email, 'General Employee')

        doc_id = str(uuid.uuid4())
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
                review_status, extracted_text, uploaded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_id, user_id, original_name, file_path, file_size, file_type,
            mime_type, datetime.datetime.utcnow().isoformat(), status, doc_type, dept,
            priority, 0.85, 1, 'en', '["' + doc_type + '", "' + dept + '"]',
            'approved' if status == 'approved' else 'pending',
            f"Sample content for {original_name} - This is a {doc_type} document for {dept} department.", uploaded_by_name
        ))



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
        ('hr.manager@company.com', 'hr@company.com', 'New Employee Onboarding Document - Employee_Handbook.pdf', 
         '<html><body><h2>New HR Document Uploaded</h2><p>A new employee handbook has been uploaded and classified to HR department.</p><p><strong>Priority:</strong> Medium</p></body></html>',
         'doc1', 'Employee_Handbook.pdf'),
        ('noreply@idcr-system.com', 'hr.employee@company.com', 'Document Processing Complete - Policy_Update.pdf', 
         '<html><body><h2>Document Processed Successfully</h2><p>Your policy update document has been processed and approved.</p></body></html>',
         'doc2', 'Policy_Update.pdf'),
        ('hr.employee@company.com', 'hr@company.com', 'URGENT: Employee Contract Review Required', 
         '<html><body><h2>URGENT: Contract Review</h2><p>New employee contract requires immediate HR review before deadline today.</p><p><strong>Priority:</strong> High</p></body></html>',
         'doc3', 'Urgent_Employee_Contract.pdf'),

        # Finance Department emails
        ('finance.manager@company.com', 'finance@company.com', 'New Financial Document - Invoice_2024_001.pdf', 
         '<html><body><h2>New Invoice Processed</h2><p>A new invoice has been uploaded and classified to finance department.</p><p><strong>Priority:</strong> High</p></body></html>',
         'doc4', 'Invoice_2024_001.pdf'),
        ('noreply@idcr-system.com', 'finance.employee@company.com', 'Payment Processing Complete', 
         '<html><body><h2>Payment Processed</h2><p>Your expense report has been approved and payment is being processed.</p></body></html>',
         'doc5', 'Expense_Report.pdf'),
        ('finance.employee@company.com', 'finance@company.com', 'Budget Review Document Uploaded', 
         '<html><body><h2>Budget Review</h2><p>Quarterly budget review document has been uploaded for approval.</p></body></html>',
         'doc6', 'Q4_Budget_Review.xlsx'),

        # Legal Department emails  
        ('legal.manager@company.com', 'legal@company.com', 'High Priority Legal Document - Contract_ABC_Corp.pdf', 
         '<html><body><h2>URGENT: Legal Review Required</h2><p>A high priority contract document requires immediate legal attention by EOD.</p><p><strong>Priority:</strong> High</p></body></html>',
         'doc7', 'Contract_ABC_Corp.pdf'),
        ('noreply@idcr-system.com', 'legal.manager@company.com', 'New Contract Classified', 
         '<html><body><h2>Document Classification Alert</h2><p>A new contract has been automatically classified to the legal department and requires review.</p></body></html>',
         'doc8', 'Client_Contract_2024.pdf'),
        ('legal.manager@company.com', 'legal@company.com', 'Compliance Document Processing Complete', 
         '<html><body><h2>Compliance Review Complete</h2><p>All compliance documents for Q4 have been processed and approved.</p></body></html>',
         'doc9', 'Q4_Compliance_Report.pdf'),
        ('sales.manager@company.com', 'legal@company.com', 'Contract Review Required - ABC Client', 
         '<html><body><h2>Contract Review Request</h2><p>New client contract requires legal review before signing tomorrow.</p></body></html>',
         'doc10', 'ABC_Client_Contract.pdf'),

        # IT Department emails
        ('it.manager@company.com', 'it@company.com', 'IT Security Policy Update Required', 
         '<html><body><h2>Security Policy Review</h2><p>New IT security policy document uploaded for review and approval.</p></body></html>',
         'doc11', 'IT_Security_Policy.docx'),
        ('noreply@idcr-system.com', 'it.manager@company.com', 'System Update Documentation', 
         '<html><body><h2>System Documentation</h2><p>New system documentation has been uploaded to IT department.</p></body></html>',
         'doc12', 'System_Update_Docs.pdf'),

        # Sales Department emails
        ('sales.manager@company.com', 'sales@company.com', 'New Sales Proposal Uploaded', 
         '<html><body><h2>Sales Proposal</h2><p>New client proposal document has been uploaded for review.</p></body></html>',
         'doc13', 'Client_Proposal_2024.pdf'),

        # General/Admin emails
        ('admin@company.com', 'general.employee@company.com', 'Welcome to IDCR System', 
         '<html><body><h2>Welcome to IDCR System!</h2><p>Your account has been successfully created. You can now upload and manage documents.</p></body></html>',
         None, None),
        ('noreply@idcr-system.com', 'admin@company.com', 'System Status Report', 
         '<html><body><h2>Weekly System Report</h2><p>This week: 25 documents processed, 20 approved, 5 pending review.</p></body></html>',
         None, None),

        # Inter-department communications
        ('hr.manager@company.com', 'finance@company.com', 'Payroll Document Review Required', 
         '<html><body><h2>Payroll Review</h2><p>Monthly payroll document requires finance department approval.</p></body></html>',
         'doc14', 'Monthly_Payroll.xlsx'),
        ('finance.manager@company.com', 'legal@company.com', 'Financial Agreement Legal Review', 
         '<html><body><h2>Legal Review Request</h2><p>New financial agreement requires legal department review before execution.</p></body></html>',
         'doc15', 'Financial_Agreement_2024.pdf'),
        ('legal.manager@company.com', 'hr@company.com', 'Employment Contract Template Updated', 
         '<html><body><h2>Contract Template Update</h2><p>The employment contract template has been updated with new legal requirements.</p></body></html>',
         'doc16', 'Employment_Contract_Template.docx'),

        # Document status notifications
        ('hr.manager@company.com', 'hr.employee@company.com', 'Document Approved - Employee Policy Update', 
         '<html><body><h2>Document Approved</h2><p>Your submitted policy update document has been approved and is now active.</p></body></html>',
         'doc17', 'Policy_Update.docx'),
        ('legal.manager@company.com', 'sales.manager@company.com', 'Contract Review Complete - Terms Accepted', 
         '<html><body><h2>Contract Review Complete</h2><p>Legal review of the ABC client contract is complete. Terms are acceptable.</p></body></html>',
         'doc18', 'ABC_Contract_Final.pdf'),
        ('finance.manager@company.com', 'hr.manager@company.com', 'Budget Approval Complete', 
         '<html><body><h2>Budget Approved</h2><p>The HR department budget for Q1 has been approved by finance.</p></body></html>',
         'doc19', 'HR_Q1_Budget.xlsx')
    ]

    for sent_by, received_by, subject, body, doc_id, file_name in sample_emails:
        email_id = str(uuid.uuid4())
        # Create emails from the past few days
        sent_time = datetime.datetime.utcnow() - datetime.timedelta(days=random.randint(0, 7), hours=random.randint(0, 23))
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


# Mount uploads directory first
app.mount("/uploads",
          StaticFiles(directory="uploads"),
          name="uploads")

@app.get("/")
async def serve_frontend():
    """Serve the main frontend application"""
    return FileResponse("index.html", media_type="text/html")

@app.exception_handler(404)
async def custom_404_handler(request, exc):
    """Custom 404 handler to prevent HTML responses for API calls"""
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return FileResponse("index.html", media_type="text/html")

@app.get("/index.html")
async def serve_index():
    """Alternative path to serve frontend"""
    return FileResponse("index.html", media_type="text/html")

@app.get("/app")
async def serve_app():
    """Another path to serve frontend"""
    return FileResponse("index.html", media_type="text/html")


@app.get("/favicon.ico")
async def favicon():
    return {"message": "No favicon"}


# Authentication endpoints
@app.post("/api/register")
async def register_user(user_data: UserRegistration):
    """Register a new user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if user already exists
        cursor.execute('SELECT user_id FROM users WHERE email = ?',
                       (user_data.email, ))
        if cursor.fetchone():
            conn.close()
            return JSONResponse(
                status_code=400,
                content={"detail": "Email already registered"},
                headers={"Content-Type": "application/json"}
            )

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

        return JSONResponse(
            content={"message": "User registered successfully", "user_id": user_id},
            headers={"Content-Type": "application/json"}
        )

    except Exception as e:
        print(f"Registration error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Registration failed - server error"},
            headers={"Content-Type": "application/json"}
        )


@app.post("/api/login")
async def login_user(user_data: UserLogin):
    """Login user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ? AND is_active = 1',
                       (user_data.email, ))
        user = cursor.fetchone()
        conn.close()

        if not user or not verify_password(user_data.password, user[2]):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid email or password"},
                headers={"Content-Type": "application/json"}
            )

        access_token = create_access_token(data={"sub": user[0]})

        return JSONResponse(
            content={
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "user_id": user[0],
                    "email": user[1],
                    "full_name": user[3],
                    "department": user[4],
                    "role": user[5]
                }
            },
            headers={"Content-Type": "application/json"}
        )

    except Exception as e:
        print(f"Login error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Login failed - server error"},
            headers={"Content-Type": "application/json"}
        )


@app.get("/api/me")
async def get_current_user_info(
        current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return JSONResponse(
        content=current_user,
        headers={"Content-Type": "application/json"}
    )


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

    # Validate file types - only allow PDF, DOC, DOCX, TXT
    allowed_types = {
        'application/pdf',
        'text/plain',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword'  # For older .doc files
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
            file_size = len(content)

            # Get user's readable name
            uploaded_by_name = current_user.get('full_name', 'General Employee')

            # Save file to disk
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            # Create document record
            cursor.execute(
                '''
                INSERT INTO documents (
                    doc_id, user_id, original_name, file_path, file_size, file_type, 
                    mime_type, uploaded_at, processing_status, extracted_text, uploaded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
                (doc_id, current_user['user_id'], file.filename, file_path,
                 file_size, file.filename.split('.')[-1].lower(),
                 file.content_type, datetime.datetime.utcnow().isoformat(), 'uploaded', content, uploaded_by_name))

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

            # Read file content for classification
            try:
                file_path = doc_row[3]
                content = ""

                if doc_row[6] == 'application/pdf':
                    # Handle PDF files
                    try:
                        import PyPDF2
                        with open(file_path, 'rb') as pdf_file:
                            pdf_reader = PyPDF2.PdfReader(pdf_file)
                            text_content = []
                            for page in pdf_reader.pages[:5]:  # Limit to first 5 pages
                                text_content.append(page.extract_text())
                            content = '\n'.join(text_content)
                    except Exception as pdf_error:
                        print(f"PDF reading error: {pdf_error}")
                        content = f"PDF document with {len(open(file_path, 'rb').read())} bytes"

                elif doc_row[6] == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                    # Handle DOCX files
                    try:
                        import docx
                        doc = docx.Document(file_path)
                        paragraphs = []
                        for para in doc.paragraphs[:50]:  # Limit to first 50 paragraphs
                            if para.text.strip():
                                paragraphs.append(para.text.strip())
                        content = '\n'.join(paragraphs)
                    except Exception as docx_error:
                        print(f"DOCX reading error: {docx_error}")
                        content = f"DOCX document: {doc_row[2]} - Content extraction failed"

                elif doc_row[6] in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                    # Handle Excel files (XLS/XLSX)
                    #The file type of excel are not validated and uploaded on the server so no need to handle it here.
                    pass

                elif doc_row[6] == 'application/msword':
                    # Handle older DOC files
                    try:
                        doc = docx.Document(file_path)
                        paragraphs = []
                        for para in doc.paragraphs[:50]:  # Limit to first 50 paragraphs
                            if para.text.strip():
                                paragraphs.append(para.text.strip())
                        content = '\n'.join(paragraphs)
                    except Exception as docx_error:
                        print(f"DOC reading error: {docx_error}")
                        content = f"DOC document: {doc_row[2]} - Content extraction failed"

                elif doc_row[6].startswith('text/'):
                    # Handle text files
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()[:10000]  # Limit to 10KB

                elif doc_row[6].startswith('image/'):
                    # Handle image files with basic OCR attempt
                    #The file type of images are not validated and uploaded on the server so no need to handle it here.
                    pass

                else:
                    # Other file types
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()[:5000]  # Limit to 5KB
                    except:
                        content = f"Binary file: {doc_row[2]} - Content type: {doc_row[6]}"

            except Exception as e:
                print(f"File reading error: {e}")
                content = f"Error reading file: {doc_row[2]}"

            # Simple local classification (fallback if microservice not available)
            classification_result = classify_document_locally(content, doc_row[2])

            # Try to use microservice if available, otherwise use local classification
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Test if microservice is available
                    health_response = await client.get(CLASSIFICATION_SERVICE_URL + "/ping")
                    if health_response.status_code == 200:
                        with open(doc_row[3], 'rb') as f:
                            files_payload = {"file": (doc_row[2], f, doc_row[6])}
                            response = await client.post(
                                CLASSIFICATION_SERVICE_URL + "/classify", 
                                files=files_payload
                            )

                            if response.status_code == 200:
                                microservice_result = response.json()
                                # Merge microservice result with local classification
                                classification_result.update({
                                    "doc_type": microservice_result.get("doc_type", classification_result["doc_type"]),
                                    "confidence": microservice_result.get("confidence", classification_result["confidence"])
                                })
                                print(f"Used microservice classification for {doc_row[2]}")
                    else:
                        print(f"Classification microservice not responding, using local classification")
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

    # Enhanced priority classification keywords
    high_priority_keywords = [
        # Deadlines
        "by EOD", "by end of day", "by today", "asap", "urgent", "immediate", "within 24 hours", 
        "deadline today", "due today", "respond by", "reply immediately", "EOD", "end of day", "today",
        # Action Requests
        "action required", "requires immediate attention", "please review urgently", "high priority", 
        "critical issue", "resolve now", "immediate action", "urgent response",
        # Escalations / Issues
        "escalated", "service disruption", "breach", "incident", "system down", "customer complaint", 
        "payment failed", "critical error", "emergency", "outage", "security breach",
        # Meetings / Events
        "today's meeting", "final review", "must attend", "confirmation needed", "urgent meeting"
    ]

    medium_priority_keywords = [
        # Follow-ups
        "reminder", "follow up", "this week", "pending", "awaiting response", "check status", 
        "update needed", "follow-up", "status update",
        # Upcoming Deadlines
        "by tomorrow", "due in 2 days", "schedule by", "before Friday", "complete by", "ETA",
        "due this week", "by end of week", "within 3 days",
        # Meetings
        "scheduled for", "calendar invite", "tentative", "planned discussion", "agenda",
        "meeting request", "schedule meeting",
        # Tasks
        "work in progress", "assigned", "need update", "submit by", "to be reviewed",
        "in progress", "task assigned", "please review"
    ]

    low_priority_keywords = [
        # FYI / Reference
        "for your information", "no action needed", "for record", "just sharing", 
        "reference document", "read only", "optional", "fyi", "for reference",
        # Long-Term
        "next quarter", "next month", "future release", "roadmap", "tentative plan", 
        "long-term goal", "backlog item", "future consideration",
        # General Updates
        "weekly summary", "monthly report", "feedback", "draft version", "notes", 
        "not urgent", "informational", "general update"
    ]

    # Enhanced priority determination with weighted scoring
    priority_score = 0
    matched_keywords = []

    # Check for high priority keywords (score +3 each)
    for keyword in high_priority_keywords:
        if keyword.lower() in content_lower or keyword.lower() in filename_lower:
            priority_score += 3
            matched_keywords.append(keyword)

    # Check for medium priority keywords (score +2 each)
    for keyword in medium_priority_keywords:
        if keyword.lower() in content_lower or keyword.lower() in filename_lower:
            priority_score += 2
            matched_keywords.append(keyword)

    # Check for low priority keywords (score +1 each, but caps at low)
    for keyword in low_priority_keywords:
        if keyword.lower() in content_lower or keyword.lower() in filename_lower:
            priority_score += 1
            matched_keywords.append(keyword)

    # Determine final priority based on score
    if priority_score >= 6:  # Multiple high priority indicators
        keyword_priority = "high"
    elif priority_score >= 3:  # At least one high priority or multiple medium
        keyword_priority = "high" if any(kw.lower() in content_lower for kw in high_priority_keywords[:10]) else "medium"
    elif priority_score >= 2:  # Medium priority indicators
        keyword_priority = "medium"
    elif priority_score >= 1:  # Low priority indicators or no matches
        keyword_priority = "low"
    else:
        keyword_priority = "low"  # Default

    # Enhanced classification for all departments with comprehensive keywords
    classification_rules = [
        # Human Resources - Comprehensive Keywords
        {
            "keywords": ["hr", "human resources", "employee relations", "talent acquisition", "recruitment", "onboarding", "performance management", "compensation & benefits", "payroll", "employee engagement", "training & development", "succession planning", "workforce planning", "hr policies", "diversity & inclusion", "labor relations", "employee retention", "hris", "human resources information system", "benefits administration", "workplace safety", "employee", "personnel", "hiring", "training", "performance", "benefits", "leave", "vacation", "sick leave", "maternity", "paternity", "disciplinary", "termination", "resignation", "promotion", "performance review", "appraisal", "job description", "organizational chart", "employee handbook", "workplace policy", "harassment", "diversity", "inclusion", "staff", "workforce", "compensation", "salary review", "performance evaluation", "employee satisfaction", "team building", "skill development", "career development"],
            "filename_keywords": ["hr", "human resources", "employee", "personnel", "hiring", "recruitment", "training", "benefits", "leave", "performance", "onboarding", "handbook", "policy", "staff", "workforce", "compensation", "evaluation", "talent", "payroll", "engagement"],
            "doc_type": "hr_document",
            "department": "hr",
            "confidence": 0.95,
            "base_priority": "medium",
            "tags": ["hr", "employee", "personnel"]
        },
        # Finance - Comprehensive Keywords
        {
            "keywords": ["finance", "financial planning", "budgeting", "accounting", "financial reporting", "accounts payable", "accounts receivable", "general ledger", "cash flow", "profit & loss", "balance sheet", "financial analysis", "treasury", "tax compliance", "auditing", "cost management", "revenue forecasting", "capital expenditure", "financial risk management", "erp", "enterprise resource planning", "invoice", "payment", "bill", "receipt", "expense", "revenue", "profit", "loss", "tax", "audit", "salary", "wage", "reimbursement", "cost", "expenditure", "vendor payment", "purchase order", "transaction", "bank statement", "credit", "debit", "financial", "fiscal", "budget", "expenditures"],
            "filename_keywords": ["finance", "financial", "budget", "accounting", "invoice", "bill", "receipt", "payment", "expense", "tax", "audit", "payroll", "cost", "purchase", "transaction", "bank", "credit", "debit", "treasury", "revenue", "profit", "loss"],
            "doc_type": "financial_document",
            "department": "finance",
            "confidence": 0.95,
            "base_priority": "high",
            "tags": ["finance", "accounting", "financial"]
        },
        # Legal - Comprehensive Keywords
        {
            "keywords": ["legal", "compliance", "contracts", "corporate governance", "litigation", "regulatory affairs", "intellectual property", "ip", "risk management", "employment law", "data privacy", "gdpr", "general data protection regulation", "legal counsel", "dispute resolution", "due diligence", "mergers & acquisitions", "m&a", "corporate law", "legal documentation", "policy compliance", "contract", "agreement", "terms", "policy", "regulation", "lawsuit", "copyright", "trademark", "patent", "non-disclosure", "nda", "privacy policy", "terms of service", "liability", "warranty", "indemnification", "arbitration", "clause", "amendment", "addendum", "legal notice", "cease and desist", "attorney", "lawyer", "court", "judge", "settlement"],
            "filename_keywords": ["legal", "contract", "agreement", "terms", "compliance", "policy", "nda", "lawsuit", "patent", "copyright", "trademark", "liability", "amendment", "litigation", "gdpr", "governance", "regulatory", "intellectual property"],
            "doc_type": "legal_document",
            "department": "legal",
            "confidence": 0.95,
            "base_priority": "high",
            "tags": ["legal", "contract", "compliance"]
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
                "tags": rule["tags"] + matched_keywords[:3],  # Add up to 3 matched keywords
                "priority_keywords": matched_keywords[:5]  # Track matched priority keywords
            }

    # Default classification
    return {
        "doc_type": "general_document",
        "department": "general",
        "confidence": 0.5,
        "priority": keyword_priority,  # Use keyword-based priority even for general docs
        "extracted_text": content[:1000],
        "page_count": 1,
        "language": "en",
        "tags": ["general"] + matched_keywords[:3],  # Add matched keywords
        "priority_keywords": matched_keywords[:5]  # Track matched priority keywords
    }


async def notify_department(doc_id: str, classification_result: dict,
                            user: dict):
    """Send notification to department about new document"""
    department = classification_result.get('department', 'general')

    # Get department email and document details
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT dept_email FROM departments WHERE dept_id = ?',
                   (department, ))
    dept_result = cursor.fetchone()

    cursor.execute('SELECT original_name FROM documents WHERE doc_id = ?', (doc_id,))
    doc_result = cursor.fetchone()
    file_name = doc_result[0] if doc_result else "Unknown"
    conn.close()

    if dept_result:
        dept_email = dept_result[0]

        # Create better description based on document type
        doc_type_desc = {
            'financial_document': 'Financial Document (Invoice/Receipt/Payment)',
            'legal_document': 'Legal Document (Contract/Agreement)',
            'hr_document': 'HR Document (Employee/Personnel)',
            'it_document': 'IT Document (Technical/System)',
            'sales_document': 'Sales Document (Proposal/Order)',
            'marketing_document': 'Marketing Document (Campaign/Content)',
        }.get(classification_result.get('doc_type', ''), classification_result.get('doc_type', 'Document'))

        # Send email notification to department
        subject = f"New {doc_type_desc} Uploaded - {file_name}"
        body = f"""
        <html>
            <body>
                <h2>📄 New Document Uploaded for Review</h2>
                <p><strong>👤 Uploaded by:</strong> {user['full_name']} ({user['email']})</p>
                <p><strong>📄 Document:</strong> {file_name}</p>
                <p><strong>🏷️ Document Type:</strong> {doc_type_desc}</p>
                <p><strong>🏢 Routed to:</strong> {department.title()} Department</p>
                <p><strong>⚡ Priority:</strong> {classification_result.get('priority', 'Medium').title()}</p>
                <p><strong>🎯 Confidence:</strong> {classification_result.get('confidence', 0):.1%}</p>
                <p><strong>🆔 Document ID:</strong> {doc_id}</p>
                <p>Please log into the IDCR system to review this document.</p>
                <p>Best regards,<br>🤖 IDCR Automated System</p>
            </body>
        </html>
        """

        # Send to department
        send_email(dept_email, subject, body, doc_id, file_name, user['email'])

        # Also send confirmation email to the uploader
        confirmation_subject = f"Document Upload Confirmation - {file_name}"
        confirmation_body = f"""
        <html>
            <body>
                <h2>✅ Document Upload Successful</h2>
                <p>Dear {user['full_name']},</p>
                <p>Your document <strong>{file_name}</strong> has been successfully uploaded and routed to the <strong>{department.title()}</strong> department.</p>
                <p><strong>Document Details:</strong></p>
                <ul>
                    <li><strong>Document Type:</strong> {doc_type_desc}</li>
                    <li><strong>Priority:</strong> {classification_result.get('priority', 'Medium').title()}</li>
                    <li><strong>Department:</strong> {department.title()}</li>
                    <li><strong>Document ID:</strong> {doc_id}</li>
                </ul>
                <p>You will receive another notification once the document has been reviewed by the department.</p>
                <p>Best regards,<br>🤖 IDCR Automated System</p>
            </body>
        </html>
        """

        # Send confirmation to uploader
        send_email(user['email'], confirmation_subject, confirmation_body, doc_id, file_name, "noreply@idcr-system.com")


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


@app.post("/api/logout")
async def logout():
    """Logout endpoint"""
    return {"message": "Logged out successfully"}

@app.post("/api/review-document/{doc_id}")
async def review_document(
    doc_id: str,
    review_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Review a document (approve/reject)"""
    if current_user.get('role') != 'manager':
        raise HTTPException(status_code=403, detail="Only managers can review documents")

    action = review_data.get('action')  # 'approve' or 'reject'
    comments = review_data.get('comments', '')

    if action not in ['approve', 'reject']:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Verify document belongs to manager's department
    cursor.execute("""
        SELECT department, uploaded_by, original_name 
        FROM documents 
        WHERE doc_id = ?
    """, [doc_id])

    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")

    doc_department, uploaded_by, file_name = result

    if doc_department != current_user.get('department'):
        conn.close()
        raise HTTPException(status_code=403, detail="You can only review documents from your department")

    # Update document status
    new_status = 'approved' if action == 'approve' else 'rejected'
    cursor.execute("""
        UPDATE documents 
        SET processing_status = ?, reviewed_by = ?, reviewed_at = ?, review_comments = ?
        WHERE doc_id = ?
    """, [new_status, current_user.get('email'), datetime.datetime.utcnow().isoformat(), comments, doc_id])

    conn.commit()

    # Get uploader's email for notification - uploaded_by might be user_id or name
    if uploaded_by:
        # First try to find by user_id
        cursor.execute("SELECT email, full_name FROM users WHERE user_id = ?", [uploaded_by])
        uploader_result = cursor.fetchone()

        if not uploader_result:
            # If not found by user_id, try to find by full_name
            cursor.execute("SELECT email, full_name FROM users WHERE full_name = ?", [uploaded_by])
            uploader_result = cursor.fetchone()
    else:
        uploader_result = None

    conn.close()

    # Send email notification to uploader
    if uploader_result:
        uploader_email = uploader_result[0]
        uploader_name = uploader_result[1] if len(uploader_result) > 1 else uploader_email
        subject = f"Document Review Update - {action.title()}"
        status_msg = "approved" if action == 'approve' else "rejected"

        body = f"""
        <html>
            <body>
                <h2>Document Review Update</h2>
                <p>Dear {uploader_name},</p>
                <p>Your document has been <strong>{status_msg}</strong>.</p>

                <h3>Document Details:</h3>
                <ul>
                    <li><strong>File Name:</strong> {file_name}</li>
                    <li><strong>Document ID:</strong> {doc_id}</li>
                    <li><strong>Status:</strong> {status_msg.title()}</li>
                    <li><strong>Reviewed by:</strong> {current_user.get('email')}</li>
                    <li><strong>Review Date:</strong> {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}</li>
                </ul>

                {f'<p><strong>Comments:</strong> {comments}</p>' if comments else ''}

                <p>Best regards,<br>IDCR System</p>
            </body>
        </html>
        """

        try:
            send_email(uploader_email, subject, body, doc_id, file_name, current_user.get('email'))
            print(f"Review notification sent to {uploader_email} for document {doc_id}")
        except Exception as e:
            print(f"Failed to send review notification: {e}")

    return {
        "message": f"Document {action}d successfully",
        "doc_id": doc_id,
        "status": new_status
    }

@app.get("/api/documents", response_model=DocumentListResponse)
async def get_documents(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    doc_type: str = None,
    department: str = None,
    search: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get paginated list of documents with filtering"""
    conn = sqlite3.connect(DB_PATH)
    cursor =conn.cursor()

    # Build query with filters
    where_clauses = []
    params = []

    # If user is not admin, only show their documents or documents in their department
    if current_user['role'] != 'admin':
        if current_user['role'] == 'employee':
            where_clauses.append("user_id = ?")
            params.append(current_user['user_id'])
        else:  # department manager - only show documents from their department
            where_clauses.append("department = ?")
            params.append(current_user['department'])

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

    # Get paginated results
    offset = (page - 1) * page_size
    query = f'''
        SELECT doc_id, original_name, file_size, file_type, uploaded_at, 
               processing_status, document_type, department, priority, 
               classification_confidence, page_count, tags, review_status, reviewed_by
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
        doc = DocumentInfo(doc_id=row[0],
                           original_name=row[1],
                           file_size=row[2],
                           file_type=row[3],
                           uploaded_at=row[4],
                           processing_status=row[5],
                           document_type=row[6] or "",
                           department=row[7] or "",
                           priority=row[8] or "",
                           classification_confidence=row[9] or 0.0,
                           page_count=row[10] or 0,
                           tags=tags,
                           review_status=row[12] or "",
                           reviewed_by=row[13] or "")
        documents.append(doc)

    return DocumentListResponse(documents=documents,
                                total_count=total_count,
                                page=page,
                                page_size=page_size)


@app.get("/api/review-documents")
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
    elif current_user['role'] == 'manager' and current_user['department'] in ['hr', 'legal', 'finance']:
        # Only HR, Legal, Finance managers can review documents routed to their department
        where_clauses.append("d.department = ?")
        params.append(current_user['department'])
    else:
        # Regular employees and other department managers cannot access review documents
        # Return empty result set
        where_clauses.append("1 = 0")  # This will return no results

    if review_status:
        where_clauses.append("d.review_status = ?")
        params.append(review_status)
    else:
        # Default to pending if no status specified
        where_clauses.append("(d.review_status IS NULL OR d.review_status = 'pending')")

    if search:
        where_clauses.append("(d.original_name LIKE ? OR d.extracted_text LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Get documents with user information
    query = f'''
        SELECT d.doc_id, d.original_name, d.file_size, d.file_type, d.uploaded_at, 
               d.processing_status, d.document_type, d.department, d.priority, 
               d.classification_confidence, d.page_count, d.tags, d.review_status, 
               d.reviewed_by, d.user_id, u.full_name as uploaded_by_name, u.email as uploaded_by_email, d.review_comments
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
            "uploaded_by": row[15] or "General Employee",
            "uploaded_by_email": row[16] or "",
            "review_comments": row[17] or ""
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

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")

    # Check permissions - allow managers to view documents in their department for review
    if current_user['role'] == 'employee' and row[1] != current_user['user_id']:
        conn.close()
        raise HTTPException(status_code=403, detail="Access denied")

    # Get user information
    cursor.execute('SELECT full_name, email FROM users WHERE user_id = ?', (row[1],))
    user_info = cursor.fetchone()
    conn.close()

    # Convert row to dictionary
    columns = [
        'doc_id', 'user_id', 'original_name', 'file_path', 'file_size',
        'file_type', 'mime_type', 'uploaded_at', 'processing_status',
        'extracted_text', 'ocr_confidence', 'document_type', 'department',
        'priority', 'classification_confidence', 'page_count', 'language',
        'tags', 'assigned_to', 'reviewed_by', 'review_status',
        'review_comments', 'reviewed_at', 'uploaded_by'
    ]

    doc_dict = dict(zip(columns, row))
    if doc_dict['tags']:
        doc_dict['tags'] = json.loads(doc_dict['tags'])

    # Add user information
    if user_info:
        doc_dict['uploaded_by'] = user_info[0]
        doc_dict['uploaded_by_email'] = user_info[1]
    else:
        doc_dict['uploaded_by'] = 'Unknown User'
        doc_dict['uploaded_by_email'] = ''

    # Extract full content from file if not already extracted or if it's truncated
    file_path = doc_dict['file_path']
    full_content = ""

    if os.path.exists(file_path):
        try:
            if doc_dict['mime_type'] == 'application/pdf':
                # Handle PDF files
                try:
                    import PyPDF2
                    with open(file_path, 'rb') as pdf_file:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        text_content = []
                        for page in pdf_reader.pages:
                            text_content.append(page.extract_text())
                        full_content = '\n'.join(text_content)
                except Exception as pdf_error:
                    print(f"PDF reading error: {pdf_error}")
                    full_content = "Error reading PDF content"

            elif doc_dict['mime_type'] == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                # Handle DOCX files
                try:
                    import docx
                    doc = docx.Document(file_path)
                    paragraphs = []
                    for para in doc.paragraphs:
                        if para.text.strip():
                            paragraphs.append(para.text.strip())
                    full_content = '\n'.join(paragraphs)
                except Exception as docx_error:
                    print(f"DOCX reading error: {docx_error}")
                    full_content = "Error reading DOCX content"

            elif doc_dict['mime_type'] == 'application/msword':
                # Handle older DOC files
                try:
                    import docx
                    doc = docx.Document(file_path)
                    paragraphs = []
                    for para in doc.paragraphs:
                        if para.text.strip():
                            paragraphs.append(para.text.strip())
                    full_content = '\n'.join(paragraphs)
                except Exception as doc_error:
                    print(f"DOC reading error: {doc_error}")
                    full_content = "Error reading DOC content"

            elif doc_dict['mime_type'].startswith('text/'):
                # Handle text files
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    full_content = f.read()

            else:
                # Other file types - try to read as text
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        full_content = f.read()
                except:
                    full_content = f"Cannot preview content for file type: {doc_dict['mime_type']}"

        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            full_content = "Error reading file content"
    else:
        full_content = "File not found on disk"

    # Use full content if available, otherwise fall back to extracted_text
    doc_dict['full_content'] = full_content if full_content else doc_dict.get('extracted_text', 'No content available')

    # Generate summary if not available
    if not doc_dict.get('summary') and doc_dict.get('extracted_text'):
        sentences = doc_dict['extracted_text'].split('.')[:2]
        summary = '. '.join(sentences).strip()
        if summary and not summary.endswith('.'):
            summary += '.'
        doc_dict['summary'] = summary or 'No summary available'
    elif not doc_dict.get('summary'):
        doc_dict['summary'] = 'No summary available'

    return doc_dict

@app.get("/api/stats")
async def get_statistics(current_user: dict = Depends(get_current_user)):
    """Get system statistics based on user role and permissions"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Build WHERE clause based on user role
        base_params = []

        if current_user['role'] == 'admin':
            # Admin can see all documents
            where_base = ""
        elif current_user['role'] == 'manager':
            # Department managers see their department's documents
            where_base = "WHERE department = ?"
            base_params = [current_user['department']]
        else:
            # Regular employees see only their own documents
            where_base = "WHERE user_id = ?"
            base_params = [current_user['user_id']]

        # Get total documents
        total_query = f'SELECT COUNT(*) FROM documents {where_base}'
        cursor.execute(total_query, base_params)
        total_documents = cursor.fetchone()[0]

        # Get processed documents (classified status)
        processed_query = f'SELECT COUNT(*) FROM documents {where_base}'
        processed_params = base_params.copy()
        if where_base:
            processed_query += " AND processing_status = ?"
        else:
            processed_query += " WHERE processing_status = ?"
        processed_params.append("classified")
        cursor.execute(processed_query, processed_params)
        processed_documents = cursor.fetchone()[0]

        # Get pending documents
        pending_query = f'SELECT COUNT(*) FROM documents {where_base}'
        pending_params = base_params.copy()
        if where_base:
            pending_query += " AND processing_status IN (?, ?)"
        else:
            pending_query += " WHERE processing_status IN (?, ?)"
        pending_params.extend(["uploaded", "processing"])
        cursor.execute(pending_query, pending_params)
        pending_documents = cursor.fetchone()[0]

        # Calculate processing rate
        processing_rate = int((processed_documents / total_documents * 100)) if total_documents > 0 else 0

        # Get document types distribution
        doc_types_query = f'''
            SELECT document_type, COUNT(*) 
            FROM documents 
            {where_base}
        '''
        doc_types_params = base_params.copy()
        if where_base:
            doc_types_query += " AND document_type IS NOT NULL"
        else:
            doc_types_query += " WHERE document_type IS NOT NULL"
        doc_types_query += " GROUP BY document_type"
        cursor.execute(doc_types_query, doc_types_params)
        doc_types = dict(cursor.fetchall())

        # Get department distribution
        if current_user['role'] in ['admin', 'manager']:
            dept_query = f'''
                SELECT department, COUNT(*) 
                FROM documents 
                {where_base}
            '''
            dept_params = base_params.copy()
            if where_base:
                dept_query += " AND department IS NOT NULL"
            else:
                dept_query += " WHERE department IS NOT NULL"
            dept_query += " GROUP BY department"
            cursor.execute(dept_query, dept_params)
            departments = dict(cursor.fetchall())
        else:
            # For regular employees, only show their own department
            departments = {current_user['department']: total_documents} if total_documents > 0 else {}

        # Get priority distribution
        priority_query = f'''
            SELECT priority, COUNT(*) 
            FROM documents 
            {where_base}
        '''
        priority_params = base_params.copy()
        if where_base:
            priority_query += " AND priority IS NOT NULL"
        else:
            priority_query += " WHERE priority IS NOT NULL"
        priority_query += " GROUP BY priority"
        cursor.execute(priority_query, priority_params)
        priorities = dict(cursor.fetchall())

        # Get upload trends (last 30 days)
        trends_query = f'''
            SELECT DATE(uploaded_at) as date, COUNT(*) as count
            FROM documents 
            {where_base}
        '''
        trends_params = base_params.copy()
        if where_base:
            trends_query += " AND uploaded_at >= datetime('now', '-30 days')"
        else:
            trends_query += " WHERE uploaded_at >= datetime('now', '-30 days')"
        trends_query += " GROUP BY DATE(uploaded_at) ORDER BY date"
        cursor.execute(trends_query, trends_params)
        upload_trends = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]

        conn.close()

        # Ensure all values are properly formatted
        stats_response = {
            "total_documents": int(total_documents) if total_documents else 0,
            "processed_documents": int(processed_documents) if processed_documents else 0,
            "pending_documents": int(pending_documents) if pending_documents else 0,
            "processing_rate": int(processing_rate) if processing_rate else 0,
            "document_types": dict(doc_types) if doc_types else {},
            "departments": dict(departments) if departments else {},
            "priorities": dict(priorities) if priorities else {},
            "upload_trends": list(upload_trends) if upload_trends else []
        }

        return JSONResponse(
            content=stats_response,
            headers={"Content-Type": "application/json"}
        )

    except Exception as e:
        print(f"Stats error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        # Return empty stats as JSON to prevent script errors
        return JSONResponse(
            content={
                "total_documents": 0,
                "processed_documents": 0,
                "pending_documents": 0,
                "processing_rate": 0,
                "document_types": {},
                "departments": {},
                "priorities": {},
                "upload_trends": []
            },
            headers={"Content-Type": "application/json"}
        )

@app.get("/api/email-notifications")
async def get_email_notifications(current_user: dict = Depends(get_current_user)):
    """Get email notifications for current user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get emails sent to or from current user, including department-wide notifications
        cursor.execute('''
            SELECT e.*, d.original_name as document_name, d.department, d.priority,
                   u1.full_name as sent_by_name, u2.full_name as received_by_name
            FROM email_notifications e
            LEFT JOIN documents d ON e.doc_id = d.doc_id
            LEFT JOIN users u1 ON e.sent_by = u1.email
            LEFT JOIN users u2 ON e.received_by = u2.email
            WHERE e.sent_by = ? OR e.received_by = ? OR 
                  (e.received_by LIKE '%@company.com' AND d.department = ?)
            ORDER BY e.sent_at DESC
            LIMIT 100
        ''', (current_user['email'], current_user['email'], current_user['department']))

        emails = []
        for row in cursor.fetchall():
            # Determine email type based on sender/receiver
            email_type = "sent" if row[1] == current_user['email'] else "received"

            # Extract priority from document or subject
            priority = "medium"
            if row[12]:  # Document priority
                priority = row[12]
            elif row[3]:  # Check subject for priority keywords
                subject_lower = row[3].lower()
                if any(word in subject_lower for word in ['urgent', 'asap', 'immediate', 'high priority']):
                    priority = "high"
                elif any(word in subject_lower for word in ['reminder', 'follow up', 'pending']):
                    priority = "medium"
                else:
                    priority = "low"

            emails.append({
                "email_id": row[0],
                "sent_by": row[1] or "noreply@idcr-system.com",
                "received_by": row[2] or current_user['email'],
                "subject": row[3] or "No Subject",
                "body_preview": (row[4][:200] + "...") if row[4] and len(row[4]) > 200 else (row[4] or ""),
                "doc_id": row[5],
                "file_name": row[6] or "N/A",
                "status": row[7] or "sent",
                "sent_at": row[8] or datetime.datetime.utcnow().isoformat(),
                "document_name": row[9] or row[6] or "N/A",
                "department": row[10] or "general",
                "priority": priority,
                "sent_by_name": row[13] or "IDCR System",
                "received_by_name": row[14] or current_user.get('full_name', 'User'),
                "email_type": email_type
            })

        conn.close()

        print(f"Email notifications loaded for {current_user['email']}: {len(emails)} emails")

        return {
            "emails": emails,
            "total_count": len(emails)
        }

    except Exception as e:
        print(f"Email notifications error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to load email notifications: {str(e)}")

# Main startup
if __name__ == "__main__":
    print("🚀 Starting IDCR Demo Server...")
    print("📂 Frontend available at: http://0.0.0.0:5000")
    print("📊 API docs available at: http://0.0.0.0:5000/docs")

    # Initialize database before starting server
    init_database()

    uvicorn.run(app, host="0.0.0.0", port=5000)