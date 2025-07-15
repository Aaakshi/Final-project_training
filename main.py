import os
import hashlib
import secrets
import sqlite3
import smtplib
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Optional
import json
import re

import jwt
import uvicorn
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from pydantic import BaseModel
import PyPDF2
from docx import Document as DocxDocument
import pytesseract
from PIL import Image
import io
from fastapi import Header

# Import email configuration
try:
    from email_config import EMAIL_CONFIG
except ImportError:
    EMAIL_CONFIG = {
        'smtp_server': 'smtp-mail.outlook.com',
        'smtp_port': 587,
        'email': 'your_email@outlook.com',
        'password': 'your_app_password'
    }

# Constants
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
UPLOAD_DIR = Path("uploads")
DATABASE_FILE = "idcr_documents.db"

# Create directories
UPLOAD_DIR.mkdir(exist_ok=True)

# Initialize FastAPI app
app = FastAPI(title="IDCR - Intelligent Document Classification & Routing")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database setup
def init_database():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Drop all tables to ensure clean state
    cursor.execute('DROP TABLE IF EXISTS email_notifications')
    cursor.execute('DROP TABLE IF EXISTS documents')
    cursor.execute('DROP TABLE IF EXISTS users')

    # Create users table
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            department TEXT NOT NULL,
            role TEXT DEFAULT 'employee',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create documents table
    cursor.execute('''
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT UNIQUE NOT NULL,
            original_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            uploaded_by TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            batch_name TEXT,
            extracted_text TEXT,
            document_type TEXT,
            department TEXT,
            priority TEXT DEFAULT 'medium',
            processing_status TEXT DEFAULT 'uploaded',
            review_status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            review_comments TEXT,
            risk_score REAL DEFAULT 0.0,
            confidentiality_percent REAL DEFAULT 0.0,
            sentiment TEXT DEFAULT 'neutral',
            summary TEXT,
            key_phrases TEXT,
            entities TEXT,
            routed_to TEXT,
            routing_reason TEXT
        )
    ''')

    # Create email_notifications table
    cursor.execute('''
        CREATE TABLE email_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            sent_by TEXT NOT NULL,
            received_by TEXT NOT NULL,
            subject TEXT NOT NULL,
            body_preview TEXT,
            email_type TEXT DEFAULT 'notification',
            status TEXT DEFAULT 'sent',
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            document_name TEXT,
            department TEXT,
            priority TEXT DEFAULT 'medium',
            FOREIGN KEY (doc_id) REFERENCES documents (doc_id)
        )
    ''')

    # Insert demo users with proper password hashing
    demo_users = [
        ("John Admin", "admin@company.com", "admin123", "administration", "admin"),
        ("Sarah Manager", "manager@company.com", "manager123", "hr", "manager"),
        ("Mike Employee", "employee@company.com", "employee123", "finance", "employee"),
        ("Lisa HR", "hr@company.com", "hr123", "hr", "manager"),
        ("Tom Finance", "finance@company.com", "finance123", "finance", "manager"),
        ("Alice Legal", "legal@company.com", "legal123", "legal", "manager"),
        ("Bob IT", "it@company.com", "it123", "it", "manager"),
        # Additional demo users matching HTML login buttons
        ("HR Manager", "hr.manager@company.com", "password123", "hr", "manager"),
        ("HR Employee", "hr.employee@company.com", "password123", "hr", "employee"),
        ("Finance Manager", "finance.manager@company.com", "password123", "finance", "manager"),
        ("Legal Manager", "legal.manager@company.com", "password123", "legal", "manager"),
        ("General Employee", "general.employee@company.com", "password123", "administration", "employee")
    ]

    for full_name, email, password, department, role in demo_users:
        try:
            hashed_password = get_password_hash(password)
            cursor.execute('''
                INSERT INTO users (full_name, email, password_hash, department, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (full_name, email, hashed_password, department, role))
            print(f"Added user: {email}")
        except Exception as e:
            print(f"Error adding user {email}: {str(e)}")

    conn.commit()
    conn.close()
    print("Database initialized successfully with demo users")

# Authentication functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Initialize database on startup
init_database()

# Migrate database to add new columns if they don't exist
def migrate_database():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Check if new columns exist, if not add them
    cursor.execute("PRAGMA table_info(documents)")
    columns = [column[1] for column in cursor.fetchall()]

    new_columns = [
        ('risk_score', 'REAL DEFAULT 0.0'),
        ('confidentiality_percent', 'REAL DEFAULT 0.0'),
        ('sentiment', 'TEXT DEFAULT "neutral"'),
        ('summary', 'TEXT'),
        ('key_phrases', 'TEXT'),
        ('entities', 'TEXT'),
        ('routed_to', 'TEXT'),
        ('routing_reason', 'TEXT')
    ]

    for column_name, column_def in new_columns:
        if column_name not in columns:
            try:
                cursor.execute(f'ALTER TABLE documents ADD COLUMN {column_name} {column_def}')
                print(f"Added column: {column_name}")
            except Exception as e:
                print(f"Column {column_name} might already exist: {str(e)}")

    conn.commit()
    conn.close()

migrate_database()

# Pydantic models
class UserRegister(BaseModel):
    full_name: str
    email: str
    password: str
    department: str

class UserLogin(BaseModel):
    email: str
    password: str

class ReviewRequest(BaseModel):
    action: str  # 'approve' or 'reject'
    comments: str = ""

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": user[0],
        "full_name": user[1],
        "email": user[2],
        "department": user[4],
        "role": user[5]
    }

# Document processing functions
def extract_text_from_file(file_path: str, file_type: str) -> str:
    try:
        if file_type.lower() == 'pdf':
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        elif file_type.lower() in ['docx', 'doc']:
            doc = DocxDocument(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        elif file_type.lower() == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        else:
            return "Unsupported file type for text extraction"
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def classify_document(text: str, filename: str) -> tuple:
    text_lower = text.lower()
    filename_lower = filename.lower()

    # Classification logic
    if any(keyword in text_lower or keyword in filename_lower for keyword in 
           ['invoice', 'billing', 'payment', 'finance', 'receipt', 'expense', 'budget']):
        return 'invoice', 'finance', 'high'
    elif any(keyword in text_lower or keyword in filename_lower for keyword in 
             ['contract', 'agreement', 'legal', 'terms', 'conditions', 'clause']):
        return 'contract', 'legal', 'high'
    elif any(keyword in text_lower or keyword in filename_lower for keyword in 
             ['employee', 'hr', 'human resources', 'payroll', 'vacation', 'leave']):
        return 'hr_document', 'hr', 'medium'
    elif any(keyword in text_lower or keyword in filename_lower for keyword in 
             ['it', 'technical', 'software', 'hardware', 'system', 'network']):
        return 'it_document', 'it', 'medium'
    elif any(keyword in text_lower or keyword in filename_lower for keyword in 
             ['marketing', 'campaign', 'promotion', 'advertisement', 'brand']):
        return 'marketing_document', 'marketing', 'low'
    else:
        return 'general', 'administration', 'low'

def get_department_email(department: str) -> str:
    """Get the appropriate email for a department based on existing users"""
    department_emails = {
        'hr': 'hr.manager@company.com',
        'finance': 'finance.manager@company.com',
        'legal': 'legal.manager@company.com',
        'it': 'it@company.com',
        'sales': 'manager@company.com',
        'marketing': 'manager@company.com',
        'operations': 'manager@company.com',
        'support': 'manager@company.com',
        'procurement': 'manager@company.com',
        'product': 'manager@company.com',
        'administration': 'admin@company.com',
        'executive': 'admin@company.com',
        'general': 'admin@company.com'
    }
    return department_emails.get(department, 'admin@company.com')

def send_email_notification(doc_info: dict, recipient_dept: str, target_email: str = None, sender_email: str = None):
    try:
        if not target_email:
            target_email = get_department_email(recipient_dept)

        if not sender_email:
            sender_email = EMAIL_CONFIG['email']

        # Mock email sending (since we don't have real SMTP configured)
        subject = f"New Document Routed: {doc_info['original_name']}"

        body = f"""
        A new document has been automatically routed to your department.

        Document: {doc_info['original_name']}
        Type: {doc_info['document_type']}
        Priority: {doc_info['priority']}
        Uploaded by: {doc_info['uploaded_by']}
        Upload time: {doc_info['uploaded_at']}
        Department: {doc_info['department']}
        Summary: {doc_info.get('summary', 'No summary available')}
        Routing Reason: {doc_info.get('routing_reason', 'Automatically routed based on classification')}

        Please review this document in the IDCR system.
        """

        # Log email notification
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO email_notifications 
            (doc_id, sent_by, received_by, subject, body_preview, document_name, department, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_info['doc_id'], 
            sender_email, 
            target_email,
            subject,
            body[:200] + "..." if len(body) > 200 else body,
            doc_info['original_name'],
            recipient_dept,
            doc_info['priority']
        ))
        conn.commit()
        conn.close()

        print(f"Email notification logged for {target_email} in {recipient_dept} department")
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as file:
        return HTMLResponse(content=file.read())

@app.post("/api/register")
async def register_user(user: UserRegister):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Check if user already exists
    cursor.execute("SELECT * FROM users WHERE email = ?", (user.email,))
    existing_user = cursor.fetchone()
    if existing_user:
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash password and insert user
    hashed_password = get_password_hash(user.password)

    # Determine role based on email pattern
    role = "admin" if "admin" in user.email else "manager" if "manager" in user.email else "employee"

    cursor.execute('''
        INSERT INTO users (full_name, email, password_hash, department, role)
        VALUES (?, ?, ?, ?, ?)
    ''', (user.full_name, user.email, hashed_password, user.department, role))

    conn.commit()
    conn.close()

    return {"message": "User registered successfully"}

@app.post("/api/login")
async def login_user(user: UserLogin):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (user.email,))
        db_user = cursor.fetchone()
        conn.close()

        if not db_user:
            print(f"User not found: {user.email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        print(f"Found user: {db_user[1]} ({db_user[2]})")

        # Verify password
        try:
            password_valid = verify_password(user.password, db_user[3])
            if not password_valid:
                print(f"Password verification failed for user: {user.email}")
                raise HTTPException(status_code=401, detail="Invalid email or password")
        except Exception as e:
            print(f"Password verification error for {user.email}: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )

        print(f"Login successful for: {user.email}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": db_user[0],
                "full_name": db_user[1],
                "email": db_user[2],
                "department": db_user[4],
                "role": db_user[5]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.get("/api/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return current_user

@app.post("/api/bulk-upload")
async def bulk_upload_documents(
    batch_name: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    batch_id = str(uuid.uuid4())
    batch_dir = UPLOAD_DIR / batch_id
    batch_dir.mkdir(exist_ok=True)

    processed_files = []

    for file in files:
        if file.size > 10 * 1024 * 1024:  # 10MB limit
            continue

        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in ['pdf', 'doc', 'docx', 'txt']:
            continue

        doc_id = str(uuid.uuid4())
        file_path = batch_dir / file.filename

        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Extract text
        extracted_text = extract_text_from_file(str(file_path), file_extension)

        # Initialize variables to prevent UnboundLocalError
        analysis_data = {}
        routing_data = {}

        # Use microservices for processing
        try:
            # 1. Classification Service
            import requests
            import json

            try:
                classification_response = requests.post(
                    "http://localhost:8001/classify-text",
                    json={
                        "doc_id": doc_id,
                        "content": extracted_text,
                        "filename": file.filename,
                        "file_type": file_extension
                    },
                    timeout=30
                )

                if classification_response.status_code == 200:
                    classification_data = classification_response.json()
                    doc_type = classification_data.get('doc_type', 'general_document')
                    department = classification_data.get('department', 'general')
                    priority = classification_data.get('priority', 'medium')
                else:
                    # Fallback to local classification
                    doc_type, department, priority = classify_document(extracted_text, file.filename)
            except Exception as e:
                print(f"Classification service error: {str(e)}")
                # Fallback to local classification
                doc_type, department, priority = classify_document(extracted_text, file.filename)

            # 2. Content Analysis Service
            try:
                analysis_response = requests.post(
                    "http://localhost:8003/analyze",
                    json={
                        "doc_id": doc_id,
                        "content": extracted_text,
                        "filename": file.filename
                    },
                    timeout=30
                )

                if analysis_response.status_code == 200:
                    analysis_data = analysis_response.json()
                else:
                    analysis_data = {}
            except Exception as e:
                print(f"Content analysis service error: {str(e)}")
                analysis_data = {}

            # 3. Routing Engine Service
            try:
                routing_response = requests.post(
                    "http://localhost:8002/route",
                    json={
                        "doc_id": doc_id,
                        "doc_type": doc_type,
                        "department": department,
                        "priority": priority,
                        "content_summary": analysis_data.get('summary', ''),
                        "file_size": file.size,
                        "user_department": current_user['department']
                    },
                    timeout=30
                )

                if routing_response.status_code == 200:
                    routing_data = routing_response.json()
                else:
                    routing_data = {}
            except Exception as e:
                print(f"Routing engine service error: {str(e)}")
                routing_data = {}

        except Exception as e:
            print(f"Microservice error: {str(e)}")
            # Fallback to local processing
            doc_type, department, priority = classify_document(extracted_text, file.filename)
            analysis_data = {}
            routing_data = {}

        # Store content analysis data in database
        risk_score = analysis_data.get('risk_score', 0.0)
        confidentiality_percent = analysis_data.get('confidentiality_percent', 0.0)
        sentiment = analysis_data.get('sentiment', 'neutral')
        summary = analysis_data.get('summary', '')
        
        # Ensure we have a meaningful summary
        if not summary or summary.strip() == '' or len(summary.strip()) < 20:
            # Generate a basic summary from the extracted text
            if extracted_text and len(extracted_text.strip()) > 50:
                words = extracted_text.strip().split()[:35]
                summary = ' '.join(words) + ("..." if len(extracted_text.strip().split()) > 35 else ".")
            else:
                summary = f"Document '{file.filename}' processed successfully. Content classified as {doc_type} for {department} department."
        
        key_phrases = json.dumps(analysis_data.get('key_phrases', []))
        entities = json.dumps(analysis_data.get('entities', {}))

        # Get target email for routing
        target_email = get_department_email(department)

        # Send email notification with routing
        doc_info = {
            'doc_id': doc_id,
            'original_name': file.filename,
            'document_type': doc_type,
            'priority': priority,
            'uploaded_by': current_user['full_name'],
            'uploaded_at': datetime.now().isoformat(),
            'department': department,
            'summary': summary,
            'routing_reason': routing_data.get('routing_reason', 'Document automatically routed based on classification')
        }

        # Send notification to department
        send_email_notification(doc_info, department, target_email, current_user['email'])

        # Save to database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO documents 
            (doc_id, original_name, file_path, file_size, file_type, uploaded_by, 
             batch_name, extracted_text, document_type, department, priority, processing_status,
             risk_score, confidentiality_percent, sentiment, summary, key_phrases, entities, routed_to, routing_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_id, file.filename, str(file_path), file.size, file_extension,
            current_user['email'], batch_name, extracted_text, doc_type, 
            department, priority, 'classified', risk_score, confidentiality_percent, sentiment, summary,
            key_phrases, entities, target_email, routing_data.get('routing_reason', '')
        ))
        conn.commit()
        conn.close()

        # Email notification already sent above in the doc_info section

        processed_files.append({
            'filename': file.filename,
            'doc_id': doc_id,
            'type': doc_type,
            'department': department,
            'priority': priority,
            'summary': analysis_data.get('summary', ''),
            'routing_info': routing_data.get('routing_reason', '')
        })

    return {
        'message': 'Files uploaded successfully',
        'batch_id': batch_id,
        'total_files': len(processed_files),
        'processed_files': processed_files
    }

@app.get("/api/documents")
async def get_documents(
    page: int = 1,
    page_size: int = 1000,  # Show more documents per page
    search: str = "",
    status: str = "",
    doc_type: str = "",
    department: str = "",
    sort_by: str = "uploaded_at_desc",
    current_user: dict = Depends(get_current_user)
):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Build query
        query = "SELECT * FROM documents WHERE 1=1"
        params = []

        if search:
            query += " AND (original_name LIKE ? OR extracted_text LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        if status:
            query += " AND processing_status = ?"
            params.append(status)

        if doc_type:
            query += " AND document_type = ?"
            params.append(doc_type)

        if department:
            query += " AND department = ?"
            params.append(department)

        # Add user filtering for non-admin users
        if current_user['role'] != 'admin':
            if current_user['role'] == 'manager':
                # HR managers can see all departments, other managers see only their department
                if current_user['department'] == 'hr':
                    # HR managers can see all documents
                    pass
                else:
                    # Other managers see only their department documents
                    query += " AND department = ?"
                    params.append(current_user['department'])
            else:
                # Regular employees see only their own uploads
                query += " AND uploaded_by = ?"
                params.append(current_user['email'])

        # Count total
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Add sorting
        sort_mapping = {
            "uploaded_at_desc": "uploaded_at DESC",
            "uploaded_at_asc": "uploaded_at ASC", 
            "name_asc": "original_name ASC",
            "name_desc": "original_name DESC",
            "priority_desc": "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END",
            "department_asc": "department ASC"
        }
        order_clause = sort_mapping.get(sort_by, "uploaded_at DESC")

        # Add sorting without pagination to show all documents
        query += f" ORDER BY {order_clause}"

        cursor.execute(query, params)
        documents = cursor.fetchall()
        conn.close()

        # Format documents
        formatted_docs = []
        for doc in documents:
            formatted_docs.append({
                'doc_id': doc[1],
                'original_name': doc[2],
                'file_size': doc[4],
                'file_type': doc[5],
                'uploaded_by': doc[6],
                'uploaded_at': doc[7],
                'batch_name': doc[8],
                'extracted_text': doc[9],
                'document_type': doc[10],
                'department': doc[11],
                'priority': doc[12],
                'processing_status': doc[13],
                'review_status': doc[14],
                'reviewed_by': doc[15] if len(doc) > 15 else None,
                'reviewed_at': doc[16] if len(doc) > 16 else None,
                'review_comments': doc[17] if len(doc) > 17 else None,
                'risk_score': doc[18] if len(doc) > 18 else 0.0,
                'confidentiality_percent': doc[19] if len(doc) > 19 else 0.0,
                'sentiment': doc[20] if len(doc) > 20 else 'neutral',
                'summary': doc[21] if len(doc) > 21 else '',
                'key_phrases': doc[22] if len(doc) > 22 else '[]',
                'entities': doc[23] if len(doc) > 23 else '{}',
                'routed_to': doc[24] if len(doc) > 24 else '',
                'routing_reason': doc[25] if len(doc) > 25 else ''
            })

        return {
            'documents': formatted_docs,
            'total_count': total_count,
            'page': 1,
            'page_size': len(formatted_docs)
        }

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Get documents error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load documents")

@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
    doc = cursor.fetchone()
    conn.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        'doc_id': doc[1],
        'original_name': doc[2],
        'file_path': doc[3],
        'file_size': doc[4],
        'file_type': doc[5],
        'uploaded_by': doc[6],
        'uploaded_at': doc[7],
        'batch_name': doc[8],
        'extracted_text': doc[9],
        'document_type': doc[10],
        'department': doc[11],
        'priority': doc[12],
        'processing_status': doc[13],
        'review_status': doc[14],
        'reviewed_by': doc[15],
        'reviewed_at': doc[16],
        'review_comments': doc[17],
        'risk_score': doc[18] if len(doc) > 18 else 0.0,
        'confidentiality_percent': doc[19] if len(doc) > 19 else 0.0,
        'sentiment': doc[20] if len(doc) > 20 else 'neutral',
        'summary': doc[21] if len(doc) > 21 else '',
        'key_phrases': doc[22] if len(doc) > 22 else '[]',
        'entities': doc[23] if len(doc) > 23 else '{}',
        'routed_to': doc[24] if len(doc) > 24 else '',
        'routing_reason': doc[25] if len(doc) > 25 else ''
    }

@app.get("/api/review-documents")
async def get_review_documents(
    search: str = "",
    review_status: str = "",
    current_user: dict = Depends(get_current_user)
):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        query = "SELECT * FROM documents WHERE 1=1"
        params = []

        # Role-based filtering
        if current_user['role'] == 'admin':
            # Admin can see all documents
            pass
        elif current_user['role'] == 'manager':
            # All managers can see documents in their department
            # HR managers can see all departments
            if current_user['department'] != 'hr':
                query += " AND department = ?"
                params.append(current_user['department'])
        else:# Regular employees can only see their own uploaded documents
            query += " AND uploaded_by = ?"
            params.append(current_user['email'])

        if search:
            query += " AND (original_name LIKE ? OR extracted_text LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        if review_status:
            query += " AND review_status = ?"
            params.append(review_status)

        query += " ORDER BY uploaded_at DESC"

        cursor.execute(query, params)
        documents = cursor.fetchall()
        conn.close()

        formatted_docs = []
        for doc in documents:
            formatted_docs.append({
                'doc_id': doc[1],
                'original_name': doc[2],
                'file_size': doc[4],
                'file_type': doc[5],
                'uploaded_by': doc[6],
                'uploaded_at': doc[7],
                'batch_name': doc[8],
                'extracted_text': doc[9],
                'document_type': doc[10],
                'department': doc[11],
                'priority': doc[12],
                'processing_status': doc[13],
                'review_status': doc[14],
                'reviewed_by': doc[15] if len(doc) > 15 else None,
                'reviewed_at': doc[16] if len(doc) > 16 else None,
                'review_comments': doc[17] if len(doc) > 17 else None,
                'risk_score': doc[18] if len(doc) > 18 else 0.0,
                'confidentiality_percent': doc[19] if len(doc) > 19 else 0.0,
                'sentiment': doc[20] if len(doc) > 20 else 'neutral',
                'summary': doc[21] if len(doc) > 21 else '',
                'key_phrases': doc[22] if len(doc) > 22 else '[]',
                'entities': doc[23] if len(doc) > 23 else '{}',
                'routed_to': doc[24] if len(doc) > 24 else '',
                'routing_reason': doc[25] if len(doc) > 25 else ''
            })

        return {'documents': formatted_docs}

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Get review documents error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load review documents")

@app.post("/api/review-document/{doc_id}")
async def review_document(
    doc_id: str,
    review: ReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Get document details before updating
        cursor.execute('SELECT * FROM documents WHERE doc_id = ?', (doc_id,))
        document = cursor.fetchone()

        if not document:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")

        # Update review status
        new_status = 'approved' if review.action == 'approve' else 'rejected'
        cursor.execute('''
            UPDATE documents 
            SET review_status = ?, reviewed_by = ?, reviewed_at = ?, review_comments = ?
            WHERE doc_id = ?
        ''', (new_status, current_user['email'], datetime.now().isoformat(), review.comments, doc_id))

        # Send notification to the person who uploaded the document
        uploader_email = document[6]  # uploaded_by field
        doc_name = document[2]  # original_name field
        department = document[11]  # department field

        # Create email notification using the correct schema
        subject = f"Document Review: {doc_name} - {new_status.upper()}"
        body = f"""
        Your document "{doc_name}" has been {new_status} by {current_user['full_name']} ({current_user['email']}).

        Review Comments: {review.comments or 'No comments provided'}

        Reviewed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

        You can view the document details in the IDCR system.
        """

        cursor.execute('''
            INSERT INTO email_notifications 
            (doc_id, sent_by, received_by, subject, body_preview, email_type, status, document_name, department, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (doc_id, current_user['email'], uploader_email, subject, body[:200] + "..." if len(body) > 200 else body, 'document_review', 'sent', doc_name, department, document[12]))

        conn.commit()
        conn.close()

        return {'message': f'Document {review.action}d successfully and notification sent to uploader'}

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Review document error: {str(e)}")
        raise HTTPException(status_code=500, detail="Review failed. Please try again.")

@app.get("/api/email-notifications")
async def get_email_notifications(current_user: dict = Depends(get_current_user)):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Get user information for name lookup
    cursor.execute("SELECT email, full_name FROM users")
    users = {email: name for email, name in cursor.fetchall()}

    query = '''
        SELECT e.*, u.full_name as sent_by_name
        FROM email_notifications e
        LEFT JOIN users u ON e.sent_by = u.email
        WHERE 1=1
    '''
    params = []

    # Filter based on user role and department
    if current_user['role'] == 'admin':
        # Admin can see all notifications
        pass
    elif current_user['role'] == 'manager':
        # Manager can see notifications for their department
        query += " AND (e.department = ? OR e.sent_by = ? OR e.received_by = ?)"
        params.extend([current_user['department'], current_user['email'], current_user['email']])
    else:
        # Employee can see notifications sent by them OR received by them
        query += " AND (e.sent_by = ? OR e.received_by = ?)"
        params.extend([current_user['email'], current_user['email']])

    query += " ORDER BY e.sent_at DESC LIMIT 50"

    cursor.execute(query, params)
    notifications = cursor.fetchall()
    conn.close()

    formatted_notifications = []
    for notif in notifications:
        received_by_name = users.get(notif[3], notif[3])  # Get name or fallback to email

        formatted_notifications.append({
            'id': notif[0],
            'doc_id': notif[1],
            'sent_by': notif[2],
            'sent_by_name': notif[11] if notif[11] else notif[2],  # Use full name if available
            'received_by': notif[3],
            'received_by_name': received_by_name,
            'subject': notif[4],
            'body_preview': notif[5],
            'email_type': notif[6],
            'status': notif[7],
            'sent_at': notif[8],
            'document_name': notif[9],
            'department': notif[10],
            'priority': notif[12] if len(notif) > 12 else 'medium'
        })

    return {
        'emails': formatted_notifications,
        'total_count': len(formatted_notifications)
    }

@app.get("/api/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Base stats query with user filtering
    base_query = "SELECT * FROM documents WHERE 1=1"
    params = []

    if current_user['role'] != 'admin':
        if current_user['role'] == 'manager':
            base_query += " AND (uploaded_by = ? OR department = ?)"
            params.extend([current_user['email'], current_user['department']])
        else:
            base_query += " AND uploaded_by = ?"
            params.append(current_user['email'])

    # Total documents
    cursor.execute(base_query, params)
    all_docs = cursor.fetchall()
    total_documents = len(all_docs)

    # Processed documents
    processed_query = base_query + " AND processing_status IN ('classified', 'completed')"
    cursor.execute(processed_query, params)
    processed_documents = len(cursor.fetchall())

    # Pending documents
    pending_query = base_query + " AND review_status = 'pending'"
    cursor.execute(pending_query, params)
    pending_documents = len(cursor.fetchall())

    # Calculate processing rate
    processing_rate = (processed_documents / total_documents * 100) if total_documents > 0 else 0

    # Document types distribution
    doc_types = {}
    departments = {}
    priorities = {}

    for doc in all_docs:
        doc_type = doc[10] or 'unknown'
        dept = doc[11] or 'unknown'
        priority = doc[12] or 'medium'

        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        departments[dept] = departments.get(dept, 0) + 1
        priorities[priority] = priorities.get(priority, 0) + 1

    # Upload trends (last 30 days)
    cursor.execute(f'''
        {base_query} AND uploaded_at >= date('now', '-30 days')
        ORDER BY date(uploaded_at)
    ''', params)
    recent_docs = cursor.fetchall()

    upload_trends = {}
    for doc in recent_docs:
        date = doc[7][:10]  # Extract date part
        upload_trends[date] = upload_trends.get(date, 0) + 1

    # Convert to list format for charts
    trends_list = [{'date': date, 'count': count} for date, count in upload_trends.items()]

    conn.close()

    return {
        'total_documents': total_documents,
        'processed_documents': processed_documents,
        'pending_documents': pending_documents,
        'processing_rate': round(processing_rate, 1),
        'document_types': doc_types,
        'departments': departments,
        'priorities': priorities,
        'upload_trends': trends_list
    }

@app.get("/api/health")
async def health_check():
    health_status = {
        "main_service": "healthy",
        "timestamp": datetime.now().isoformat(),
        "microservices": {}
    }

    # Check microservices
    services = {
        "classification": "http://localhost:8001/ping",
        "routing_engine": "http://localhost:8002/ping", 
        "content_analysis": "http://localhost:8003/ping"
    }

    for service_name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                health_status["microservices"][service_name] = "healthy"
            else:
                health_status["microservices"][service_name] = "unhealthy"
        except:
            health_status["microservices"][service_name] = "unreachable"

    return health_status

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)