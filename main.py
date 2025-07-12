
import asyncio
import subprocess
import sys
import time
import signal
import os
import sqlite3
import json
import smtplib
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import httpx
import uvicorn
import uuid
import jwt

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
    EMAIL_USER = "your-email@outlook.com"  # Replace with your Outlook email
    EMAIL_PASSWORD = "your-app-password"  # Replace with your app password

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
    
    # Insert default departments
    default_departments = [
        ('finance', 'Finance Department', 'finance@company.com', 'finance.manager@company.com'),
        ('legal', 'Legal Department', 'legal@company.com', 'legal.manager@company.com'),
        ('hr', 'Human Resources', 'hr@company.com', 'hr.manager@company.com'),
        ('it', 'IT Department', 'it@company.com', 'it.manager@company.com'),
        ('general', 'General Department', 'general@company.com', 'general.manager@company.com')
    ]
    
    for dept in default_departments:
        cursor.execute('''
            INSERT OR IGNORE INTO departments (dept_id, dept_name, dept_email, manager_email)
            VALUES (?, ?, ?, ?)
        ''', dept)
    
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
    
    conn.commit()
    conn.close()
    print("✓ Database initialized")

# Initialize database on startup
init_database()

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
    document_type: str = None
    department: str = None
    priority: str = None
    classification_confidence: float = None
    page_count: int = None
    tags: List[str] = None
    review_status: str = None
    reviewed_by: str = None

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
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ? AND is_active = 1', (user_id,))
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

def send_email(to_email: str, subject: str, body: str):
    """Send email using Outlook SMTP"""
    try:
        msg = MimeMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MimeText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_USER, to_email, text)
        server.quit()
        
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {str(e)}")
        return False

# Mount static files
app.mount("/static", StaticFiles(directory="Final-project_training"), name="static")

@app.get("/")
async def serve_frontend():
    """Serve the main frontend application"""
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
    cursor.execute('SELECT user_id FROM users WHERE email = ?', (user_data.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user_id = str(uuid.uuid4())
    password_hash = hash_password(user_data.password)
    
    cursor.execute('''
        INSERT INTO users (user_id, email, password_hash, full_name, department, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, user_data.email, password_hash, user_data.full_name, 
          user_data.department or 'general', datetime.utcnow().isoformat()))
    
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
    send_email(user_data.email, "Welcome to IDCR System", welcome_body)
    
    return {"message": "User registered successfully", "user_id": user_id}

@app.post("/api/login")
async def login_user(user_data: UserLogin):
    """Login user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE email = ? AND is_active = 1', (user_data.email,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not verify_password(user_data.password, user[2]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
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
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
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
                status[service] = "healthy" if response.status_code == 200 else "unhealthy"
            except Exception as e:
                status[service] = f"offline: {str(e)}"
    
    return {"services": status}

@app.post("/api/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_documents(
    files: List[UploadFile] = File(...), 
    batch_name: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Handle bulk document upload (up to 20+ files)"""
    
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Too many files. Maximum 50 files per batch.")
    
    # Validate file types
    allowed_types = {
        'application/pdf', 'text/plain',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'image/jpeg', 'image/png', 'image/tiff'
    }
    
    # Validate files
    for file in files:
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file.content_type} for file {file.filename}"
            )
        
        # Check file size (10MB limit per file)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {file.filename} (Max 10MB per file)"
            )
        # Reset file pointer
        await file.seek(0)
    
    batch_id = str(uuid.uuid4())
    upload_dir = f"uploads/{batch_id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Create batch record
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO upload_batches (batch_id, user_id, batch_name, total_files, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (batch_id, current_user['user_id'], batch_name, len(files), datetime.utcnow().isoformat()))
    
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
            cursor.execute('''
                INSERT INTO documents (
                    doc_id, user_id, original_name, file_path, file_size, file_type, 
                    mime_type, uploaded_at, processing_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                doc_id, current_user['user_id'], file.filename, file_path, len(content),
                file.filename.split('.')[-1].lower(), file.content_type,
                datetime.utcnow().isoformat(), 'uploaded'
            ))
            
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
    asyncio.create_task(process_batch_async(batch_id, saved_files, current_user))
    
    return BulkUploadResponse(
        batch_id=batch_id,
        message=f"Successfully uploaded {len(saved_files)} files",
        total_files=len(saved_files)
    )

async def process_batch_async(batch_id: str, files: List[dict], user: dict):
    """Process uploaded files asynchronously"""
    processed = 0
    failed = 0
    
    for file_info in files:
        try:
            # Get document details
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM documents WHERE doc_id = ?', (file_info['doc_id'],))
            doc_row = cursor.fetchone()
            conn.close()
            
            if not doc_row:
                continue
            
            # Update status to processing
            update_document_status(file_info['doc_id'], 'processing')
            
            # Send to classification service
            with open(doc_row[3], 'rb') as f:  # file_path is index 3
                async with httpx.AsyncClient(timeout=30.0) as client:
                    files_payload = {"file": (doc_row[2], f, doc_row[6])}  # original_name, content, mime_type
                    response = await client.post(
                        "http://0.0.0.0:8001/classify",
                        files=files_payload
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Update document with classification results
                        update_document_classification(file_info['doc_id'], result)
                        update_document_status(file_info['doc_id'], 'classified')
                        
                        # Send notification to department
                        await notify_department(file_info['doc_id'], result, user)
                        
                        processed += 1
                    else:
                        update_document_status(file_info['doc_id'], 'failed')
                        failed += 1
                        
        except Exception as e:
            print(f"Error processing document {file_info['doc_id']}: {e}")
            update_document_status(file_info['doc_id'], 'failed')
            failed += 1
    
    # Update batch status
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE upload_batches 
        SET processed_files = ?, failed_files = ?, completed_at = ?, status = ?
        WHERE batch_id = ?
    ''', (processed, failed, datetime.utcnow().isoformat(), 'completed', batch_id))
    conn.commit()
    conn.close()

async def notify_department(doc_id: str, classification_result: dict, user: dict):
    """Send notification to department about new document"""
    department = classification_result.get('department', 'general')
    
    # Get department email
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT dept_email FROM departments WHERE dept_id = ?', (department,))
    dept_result = cursor.fetchone()
    conn.close()
    
    if dept_result:
        dept_email = dept_result[0]
        
        # Send email to department
        subject = f"New Document for Review - {classification_result.get('doc_type', 'Document')}"
        body = f"""
        <html>
            <body>
                <h2>New Document Uploaded for Review</h2>
                <p><strong>Uploaded by:</strong> {user['full_name']} ({user['email']})</p>
                <p><strong>Document Type:</strong> {classification_result.get('doc_type', 'Unknown')}</p>
                <p><strong>Priority:</strong> {classification_result.get('priority', 'Medium')}</p>
                <p><strong>Confidence:</strong> {classification_result.get('confidence', 0):.2%}</p>
                <p><strong>Document ID:</strong> {doc_id}</p>
                <p>Please log into the IDCR system to review this document.</p>
                <p>Best regards,<br>IDCR System</p>
            </body>
        </html>
        """
        
        send_email(dept_email, subject, body)

def update_document_status(doc_id: str, status: str):
    """Update document processing status"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE documents SET processing_status = ? WHERE doc_id = ?', (status, doc_id))
    conn.commit()
    conn.close()

def update_document_classification(doc_id: str, classification_result: dict):
    """Update document with classification results"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tags_json = json.dumps(classification_result.get('tags', []))
    
    cursor.execute('''
        UPDATE documents SET 
            extracted_text = ?, document_type = ?, department = ?, 
            priority = ?, classification_confidence = ?, page_count = ?,
            language = ?, tags = ?
        WHERE doc_id = ?
    ''', (
        classification_result.get('extracted_text', ''),
        classification_result.get('doc_type', ''),
        classification_result.get('department', ''),
        classification_result.get('priority', ''),
        classification_result.get('confidence', 0.0),
        classification_result.get('page_count', 1),
        classification_result.get('language', 'en'),
        tags_json,
        doc_id
    ))
    
    conn.commit()
    conn.close()

@app.post("/api/documents/{doc_id}/review")
async def review_document(
    doc_id: str, 
    review: DocumentReview,
    current_user: dict = Depends(get_current_user)
):
    """Review a document (approve/reject)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get document info
    cursor.execute('SELECT user_id, original_name FROM documents WHERE doc_id = ?', (doc_id,))
    doc_result = cursor.fetchone()
    
    if not doc_result:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Update document review status
    cursor.execute('''
        UPDATE documents 
        SET review_status = ?, reviewed_by = ?, review_comments = ?, reviewed_at = ?
        WHERE doc_id = ?
    ''', (review.status, current_user['email'], review.comments, datetime.utcnow().isoformat(), doc_id))
    
    # Get user email who uploaded the document
    cursor.execute('SELECT email, full_name FROM users WHERE user_id = ?', (doc_result[0],))
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
        
        send_email(user_email, subject, body)
    
    return {"message": f"Document {review.status} successfully"}

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
            params.extend([current_user['user_id'], current_user['department']])
    
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
        doc = DocumentInfo(
            doc_id=row[0],
            original_name=row[1],
            file_size=row[2],
            file_type=row[3],
            uploaded_at=row[4],
            processing_status=row[5],
            document_type=row[6],
            department=row[7],
            priority=row[8],
            classification_confidence=row[9],
            page_count=row[10],
            tags=tags,
            review_status=row[12],
            reviewed_by=row[13]
        )
        documents.append(doc)
    
    return DocumentListResponse(
        documents=documents,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@app.get("/api/documents/{doc_id}")
async def get_document_details(doc_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed information about a specific document"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM documents WHERE doc_id = ?', (doc_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check permissions
    if current_user['role'] == 'employee' and row[1] != current_user['user_id']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Convert row to dictionary
    columns = [
        'doc_id', 'user_id', 'original_name', 'file_path', 'file_size', 'file_type', 'mime_type',
        'uploaded_at', 'processing_status', 'extracted_text', 'ocr_confidence',
        'document_type', 'department', 'priority', 'classification_confidence', 
        'page_count', 'language', 'tags', 'assigned_to', 'reviewed_by', 
        'review_status', 'review_comments', 'reviewed_at'
    ]
    
    doc_dict = dict(zip(columns, row))
    if doc_dict['tags']:
        doc_dict['tags'] = json.loads(doc_dict['tags'])
    
    return doc_dict

@app.get("/api/stats")
async def get_statistics(current_user: dict = Depends(get_current_user)):
    """Get document processing statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Build base query based on user role
    base_where = ""
    params = []
    
    if current_user['role'] == 'employee':
        base_where = "WHERE user_id = ?"
        params.append(current_user['user_id'])
    elif current_user['role'] != 'admin':
        base_where = "WHERE (user_id = ? OR department = ?)"
        params.extend([current_user['user_id'], current_user['department']])
    
    # Overall stats
    cursor.execute(f'SELECT COUNT(*) FROM documents {base_where}', params)
    total_docs = cursor.fetchone()[0]
    
    cursor.execute(f'SELECT COUNT(*) FROM documents {base_where} AND processing_status = "completed"', params)
    processed_docs = cursor.fetchone()[0]
    
    cursor.execute(f'SELECT COUNT(*) FROM documents {base_where} AND processing_status = "processing"', params)
    pending_docs = cursor.fetchone()[0]
    
    cursor.execute(f'SELECT COUNT(*) FROM documents {base_where} AND processing_status = "failed"', params)
    error_docs = cursor.fetchone()[0]
    
    # Document type breakdown
    cursor.execute(f'''
        SELECT document_type, COUNT(*) 
        FROM documents 
        {base_where} AND document_type IS NOT NULL 
        GROUP BY document_type
    ''', params)
    doc_types = dict(cursor.fetchall())
    
    # Department breakdown
    cursor.execute(f'''
        SELECT department, COUNT(*) 
        FROM documents 
        {base_where} AND department IS NOT NULL 
        GROUP BY department
    ''', params)
    departments = dict(cursor.fetchall())
    
    # Priority breakdown
    cursor.execute(f'''
        SELECT priority, COUNT(*) 
        FROM documents 
        {base_where} AND priority IS NOT NULL 
        GROUP BY priority
    ''', params)
    priorities = dict(cursor.fetchall())
    
    conn.close()
    
    return {
        "total_documents": total_docs,
        "processed_documents": processed_docs,
        "pending_documents": pending_docs,
        "error_documents": error_docs,
        "document_types": doc_types,
        "departments": departments,
        "priorities": priorities
    }

# Keep existing classification endpoint for single file processing
@app.post("/api/classify")
async def classify_document():
    """Classify document through the processing pipeline"""
    try:
        health_response = await health_check()
        if not all(status == "healthy" for status in health_response["services"].values()):
            return {"error": "Backend services not fully available", "success": False}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            classify_response = await client.post(
                "http://0.0.0.0:8001/classify",
                files={"file": ("document.txt", b"This is an invoice for $1000", "text/plain")}
            )
            
            if classify_response.status_code != 200:
                return {"error": "Classification service unavailable"}
            
            classification = classify_response.json()
            
            route_response = await client.post(
                "http://0.0.0.0:8002/route",
                json={"doc_id": "doc-123", "doc_type": classification["doc_type"]}
            )
            
            if route_response.status_code != 200:
                return {"error": "Routing service unavailable"}
            
            routing = route_response.json()
            
            analysis_response = await client.post(
                "http://0.0.0.0:8003/analyze",
                json={"doc_id": "doc-123", "content": "This is an invoice for $1000"}
            )
            
            if analysis_response.status_code != 200:
                return {"error": "Analysis service unavailable"}
            
            analysis = analysis_response.json()
            
            notify_response = await client.post(
                "http://0.0.0.0:8004/notify",
                json={"doc_id": "doc-123", "assignee": routing["assignee"]}
            )
            
            if notify_response.status_code != 200:
                return {"error": "Notification service unavailable"}
            
            notification = notify_response.json()
            
            return {
                "success": True,
                "results": {
                    "classification": classification,
                    "routing": routing,
                    "analysis": analysis,
                    "notification": notification
                }
            }
            
    except Exception as e:
        return {"error": f"Pipeline failed: {str(e)}"}

def kill_existing_processes():
    """Kill any existing processes on our target ports"""
    ports_to_check = [8000, 8001, 8002, 8003, 8004]
    
    for port in ports_to_check:
        try:
            subprocess.run([
                "pkill", "-f", f"port {port}"
            ], capture_output=True)
            
            subprocess.run([
                "pkill", "-f", f":{port}"
            ], capture_output=True)
            
            time.sleep(0.5)
        except Exception:
            pass
    
    print("Cleaned up existing processes")

def start_backend():
    """Start all microservices with proper error handling"""
    global backend_processes
    
    kill_existing_processes()
    
    print("Starting backend microservices...")
    
    services = [
        ("Final-project_training/microservices/api_gateway/app", 8000),
        ("Final-project_training/microservices/classification/app", 8001),
        ("Final-project_training/microservices/routing_engine/app", 8002),
        ("Final-project_training/microservices/content_analysis/app", 8003),
        ("Final-project_training/microservices/workflow_integration/app", 8004)
    ]
    
    backend_processes = []
    
    for service_path, port in services:
        try:
            env = os.environ.copy()
            current_dir = os.getcwd()
            project_root = os.path.join(current_dir, "Final-project_training")
            env['PYTHONPATH'] = f"{project_root}:{env.get('PYTHONPATH', '')}"
            
            process = subprocess.Popen([
                sys.executable, "-m", "uvicorn", "main:app", 
                "--host", "0.0.0.0", 
                "--port", str(port), 
                "--log-level", "error",
                "--access-log"
            ], 
            cwd=service_path, 
            env=env,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
            )
            
            backend_processes.append(process)
            print(f"✓ Started {service_path.split('/')[-1]} service on port {port}")
            time.sleep(2.5)
            
        except Exception as e:
            print(f"✗ Failed to start service {service_path}: {e}")
    
    return backend_processes

def cleanup_processes():
    """Clean up all backend processes"""
    global backend_processes
    
    print("\nShutting down backend services...")
    
    for process in backend_processes:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except:
            try:
                process.terminate()
            except:
                pass
    
    time.sleep(2)
    
    for process in backend_processes:
        try:
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except:
            try:
                process.kill()
            except:
                pass
    
    backend_processes = []
    print("Backend services stopped")

async def wait_for_services():
    """Wait for backend services to be ready"""
    print("Waiting for backend services to be ready...")
    
    services = [
        "http://0.0.0.0:8000/ping",
        "http://0.0.0.0:8001/ping", 
        "http://0.0.0.0:8002/ping",
        "http://0.0.0.0:8003/ping",
        "http://0.0.0.0:8004/ping"
    ]
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        ready_services = 0
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            for service_url in services:
                try:
                    response = await client.get(service_url)
                    if response.status_code == 200:
                        ready_services += 1
                except:
                    pass
        
        if ready_services == len(services):
            print("✓ All backend services are ready!")
            return True
        
        print(f"  {ready_services}/{len(services)} services ready...")
        await asyncio.sleep(1)
        retry_count += 1
    
    print("⚠ Some services may not be ready, but continuing...")
    return False

@app.on_event("shutdown")
def shutdown_event():
    cleanup_processes()

if __name__ == "__main__":
    def signal_handler(sig, frame):
        cleanup_processes()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print("🚀 Starting Enhanced IDCR Application")
        print("=" * 50)
        
        backend_processes = start_backend()
        asyncio.run(wait_for_services())
        
        print("\n🌐 Starting frontend server...")
        print("=" * 50)
        print("📱 Access your application at: http://0.0.0.0:5000")
        print("🔍 Backend services running on ports 8000-8004")
        print("📁 Document storage: SQLite database")
        print("⚡ Ready for bulk document processing!")
        print("🔐 User authentication enabled")
        print("📧 Email notifications configured")
        print("=" * 50)
        
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=5000,
            access_log=True,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        cleanup_processes()
    except Exception as e:
        print(f"Error starting application: {e}")
        cleanup_processes()
