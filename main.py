
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
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
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
        CREATE TABLE IF NOT EXISTS documents (
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
            review_comments TEXT
        )
    ''')
    
    # Create email_notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_notifications (
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
        ("Bob IT", "it@company.com", "it123", "it", "manager")
    ]
    
    # First, let's clear existing users to avoid conflicts
    cursor.execute("DELETE FROM users")
    
    for full_name, email, password, department, role in demo_users:
        hashed_password = get_password_hash(password)
        cursor.execute('''
            INSERT INTO users (full_name, email, password_hash, department, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (full_name, email, hashed_password, department, role))
    
    conn.commit()
    conn.close()
    print("Database initialized with demo users")

# Authentication functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Initialize database on startup
init_database()

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
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
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

def send_email_notification(doc_info: dict, recipient_dept: str):
    try:
        smtp_server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        smtp_server.starttls()
        smtp_server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = f"{recipient_dept}@company.com"
        msg['Subject'] = f"New Document Routed: {doc_info['original_name']}"
        
        body = f"""
        A new document has been automatically routed to your department.
        
        Document: {doc_info['original_name']}
        Type: {doc_info['document_type']}
        Priority: {doc_info['priority']}
        Uploaded by: {doc_info['uploaded_by']}
        Upload time: {doc_info['uploaded_at']}
        
        Please review this document in the IDCR system.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        smtp_server.send_message(msg)
        smtp_server.quit()
        
        # Log email notification
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO email_notifications 
            (doc_id, sent_by, received_by, subject, body_preview, document_name, department, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_info['doc_id'], 
            EMAIL_CONFIG['email'], 
            f"{recipient_dept}@company.com",
            msg['Subject'],
            body[:200] + "..." if len(body) > 200 else body,
            doc_info['original_name'],
            recipient_dept,
            doc_info['priority']
        ))
        conn.commit()
        conn.close()
        
        print(f"Email sent to {recipient_dept} department")
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
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (user.email,))
    db_user = cursor.fetchone()
    conn.close()
    
    if not db_user or not verify_password(user.password, db_user[3]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
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
        
        # Use microservices for processing
        try:
            # 1. Classification Service
            import requests
            import json
            
            with open(file_path, 'rb') as f:
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
                
                analysis_data = {}
                if analysis_response.status_code == 200:
                    analysis_data = analysis_response.json()
            except:
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
                
                routing_data = {}
                if routing_response.status_code == 200:
                    routing_data = routing_response.json()
            except:
                routing_data = {}
            
        except Exception as e:
            print(f"Microservice error: {str(e)}")
            # Fallback to local processing
            doc_type, department, priority = classify_document(extracted_text, file.filename)
        
        # Save to database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO documents 
            (doc_id, original_name, file_path, file_size, file_type, uploaded_by, 
             batch_name, extracted_text, document_type, department, priority, processing_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_id, file.filename, str(file_path), file.size, file_extension,
            current_user['email'], batch_name, extracted_text, doc_type, 
            department, priority, 'classified'
        ))
        conn.commit()
        conn.close()
        
        # Send email notification
        doc_info = {
            'doc_id': doc_id,
            'original_name': file.filename,
            'document_type': doc_type,
            'priority': priority,
            'uploaded_by': current_user['full_name'],
            'uploaded_at': datetime.now().isoformat()
        }
        send_email_notification(doc_info, department)
        
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
    page_size: int = 20,
    search: str = "",
    status: str = "",
    doc_type: str = "",
    department: str = "",
    current_user: dict = Depends(get_current_user)
):
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
            query += " AND (uploaded_by = ? OR department = ?)"
            params.extend([current_user['email'], current_user['department']])
        else:
            query += " AND uploaded_by = ?"
            params.append(current_user['email'])
    
    # Count total
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]
    
    # Add pagination
    query += " ORDER BY uploaded_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    
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
            'review_status': doc[14]
        })
    
    return {
        'documents': formatted_docs,
        'total_count': total_count,
        'page': page,
        'page_size': page_size
    }

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
        'review_comments': doc[17]
    }

@app.get("/api/review-documents")
async def get_review_documents(
    search: str = "",
    review_status: str = "",
    current_user: dict = Depends(get_current_user)
):
    # Only managers and admins can review documents
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    query = "SELECT * FROM documents WHERE 1=1"
    params = []
    
    # Filter by department for managers
    if current_user['role'] == 'manager':
        query += " AND department = ?"
        params.append(current_user['department'])
    
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
            'review_status': doc[14]
        })
    
    return {'documents': formatted_docs}

@app.post("/api/review-document/{doc_id}")
async def review_document(
    doc_id: str,
    review: ReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Update review status
    new_status = 'approved' if review.action == 'approve' else 'rejected'
    cursor.execute('''
        UPDATE documents 
        SET review_status = ?, reviewed_by = ?, reviewed_at = ?, review_comments = ?
        WHERE doc_id = ?
    ''', (new_status, current_user['email'], datetime.now().isoformat(), review.comments, doc_id))
    
    conn.commit()
    conn.close()
    
    return {'message': f'Document {review.action}d successfully'}

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
        query += " AND (e.department = ? OR e.sent_by = ?)"
        params.extend([current_user['department'], current_user['email']])
    else:
        # Employee can only see their own notifications
        query += " AND e.sent_by = ?"
        params.append(current_user['email'])
    
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
