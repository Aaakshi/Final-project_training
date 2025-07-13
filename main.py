from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
import sqlite3
import hashlib
import jwt
import uuid
import os
import shutil
from datetime import datetime, timedelta
import asyncio
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email_config import EMAIL_CONFIG

# Configuration
SECRET_KEY = "your-very-secure-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

app = FastAPI(title="IDCR - Intelligent Document Classification & Routing System")
security = HTTPBearer()

# Database setup
def init_database():
    conn = sqlite3.connect('idcr_documents.db')
    cursor = conn.cursor()

    # Users table
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

    # Documents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT UNIQUE NOT NULL,
            batch_id TEXT NOT NULL,
            batch_name TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            uploaded_by INTEGER NOT NULL,
            target_department TEXT NOT NULL,
            document_type TEXT DEFAULT 'general',
            priority TEXT DEFAULT 'medium',
            review_status TEXT DEFAULT 'pending',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER,
            FOREIGN KEY (uploaded_by) REFERENCES users (id),
            FOREIGN KEY (reviewed_by) REFERENCES users (id)
        )
    ''')

    # Email notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notification_type TEXT NOT NULL
        )
    ''')

    # Insert default users if they don't exist
    default_users = [
        ('HR Manager', 'hr.manager@company.com', 'password123', 'hr', 'manager'),
        ('Finance Manager', 'finance.manager@company.com', 'password123', 'finance', 'manager'),
        ('Legal Manager', 'legal.manager@company.com', 'password123', 'legal', 'manager'),
        ('General Employee', 'general.employee@company.com', 'password123', 'general', 'employee'),
        ('Jane Smith', 'jane.smith@company.com', 'password123', 'hr', 'employee'),
        ('Admin User', 'admin@company.com', 'admin123', 'administration', 'admin')
    ]

    for name, email, password, dept, role in default_users:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute('''
            INSERT OR IGNORE INTO users (full_name, email, password_hash, department, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, email, password_hash, dept, role))

    conn.commit()
    conn.close()
    print("✓ Database initialized")

# Pydantic models
class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    department: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

# Authentication functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        conn = sqlite3.connect('idcr_documents.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
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
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Email sending function (demo mode)
async def send_email_demo(to_email: str, subject: str, body: str, notification_type: str):
    try:
        # Demo mode - just log the email
        print(f"\n📧 EMAIL NOTIFICATION (DEMO MODE)")
        print(f"From: general.employee@company.com")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body Preview: {body[:200]}...")

        # Log email to database
        conn = sqlite3.connect('idcr_documents.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO email_notifications (recipient_email, subject, body, notification_type)
            VALUES (?, ?, ?, ?)
        ''', (to_email, subject, body, notification_type))
        conn.commit()
        conn.close()

        print(f"✅ Email logged successfully (not actually sent in demo)")

    except Exception as e:
        print(f"📧 Email sending failed (expected in demo): {e}")

# API Routes
@app.post("/api/register")
async def register_user(user: UserRegister):
    conn = sqlite3.connect('idcr_documents.db')
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute('SELECT email FROM users WHERE email = ?', (user.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash password and create user
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    cursor.execute('''
        INSERT INTO users (full_name, email, password_hash, department, role)
        VALUES (?, ?, ?, ?, ?)
    ''', (user.full_name, user.email, password_hash, user.department, 'employee'))

    conn.commit()
    conn.close()

    return {"message": "User registered successfully"}

@app.post("/api/login", response_model=Token)
async def login_user(user: UserLogin):
    conn = sqlite3.connect('idcr_documents.db')
    cursor = conn.cursor()

    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    cursor.execute('''
        SELECT * FROM users WHERE email = ? AND password_hash = ?
    ''', (user.email, password_hash))

    db_user = cursor.fetchone()
    conn.close()

    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": str(db_user[0])})
    user_data = {
        "id": db_user[0],
        "full_name": db_user[1],
        "email": db_user[2],
        "department": db_user[4],
        "role": db_user[5]
    }

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }

@app.get("/api/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return current_user

@app.post("/api/bulk-upload")
async def bulk_upload(
    files: List[UploadFile] = File(...),
    batch_name: str = Form(...),
    target_department: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files allowed")

    # Validate file types
    allowed_extensions = {'.pdf', '.doc', '.docx', '.txt'}
    for file in files:
        if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
            raise HTTPException(status_code=400, detail=f"File {file.filename} has unsupported format. Only PDF, DOC, DOCX, TXT files are allowed.")

    batch_id = str(uuid.uuid4())
    upload_dir = f"uploads/{batch_id}"
    os.makedirs(upload_dir, exist_ok=True)

    conn = sqlite3.connect('idcr_documents.db')
    cursor = conn.cursor()

    uploaded_files = []

    for file in files:
        if file.size > 10 * 1024 * 1024:  # 10MB limit
            continue

        # Save file
        file_path = os.path.join(upload_dir, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Classify document (simple classification)
        document_type = classify_document(file.filename, content)
        priority = determine_priority(file.filename, content)

        # Insert into database
        doc_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO documents 
            (doc_id, batch_id, batch_name, original_name, file_path, file_size, 
             uploaded_by, target_department, document_type, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (doc_id, batch_id, batch_name, file.filename, file_path, file.size,
              current_user['id'], target_department, document_type, priority))

        uploaded_files.append({
            "filename": file.filename,
            "doc_id": doc_id,
            "type": document_type,
            "priority": priority
        })

    conn.commit()
    conn.close()

    # Send notifications to ALL department managers AND direct department emails
    await notify_department_managers(target_department, batch_name, current_user, uploaded_files)

    return {
        "message": f"Successfully uploaded {len(uploaded_files)} files",
        "batch_id": batch_id,
        "files": uploaded_files
    }

def classify_document(filename: str, content: bytes) -> str:
    filename_lower = filename.lower()
    try:
        text_content = content.decode('utf-8', errors='ignore').lower()
    except:
        text_content = ""

    # Classification logic
    if any(word in filename_lower or word in text_content for word in ['hr', 'employee', 'hiring', 'payroll']):
        return 'hr'
    elif any(word in filename_lower or word in text_content for word in ['finance', 'invoice', 'budget', 'expense']):
        return 'finance'
    elif any(word in filename_lower or word in text_content for word in ['legal', 'contract', 'agreement', 'terms']):
        return 'legal'
    elif any(word in filename_lower or word in text_content for word in ['it', 'technical', 'system', 'software']):
        return 'it'
    else:
        return 'general'

def determine_priority(filename: str, content: bytes) -> str:
    filename_lower = filename.lower()
    try:
        text_content = content.decode('utf-8', errors='ignore').lower()
    except:
        text_content = ""

    if any(word in filename_lower or word in text_content for word in ['urgent', 'critical', 'asap', 'emergency']):
        return 'high'
    elif any(word in filename_lower or word in text_content for word in ['fyi', 'info', 'reference']):
        return 'low'
    else:
        return 'medium'

async def notify_department_managers(department: str, batch_name: str, uploader: dict, files: list):
    conn = sqlite3.connect('idcr_documents.db')
    cursor = conn.cursor()

    # Get ALL managers for the target department
    cursor.execute('''
        SELECT email, full_name FROM users 
        WHERE department = ? AND (role = 'manager' OR role = 'admin')
    ''', (department,))

    managers = cursor.fetchall()

    # Also get general admins
    cursor.execute('''
        SELECT email, full_name FROM users 
        WHERE role = 'admin'
    ''')

    admins = cursor.fetchall()
    conn.close()

    # Combine managers and admins
    all_recipients = list(set(managers + admins))

    # Department email mapping
    department_emails = {
        'hr': 'hr@company.com',
        'finance': 'finance@company.com', 
        'legal': 'legal@company.com',
        'it': 'it@company.com',
        'operations': 'operations@company.com',
        'general': 'general@company.com'
    }

    # Add department email to recipients
    if department in department_emails:
        all_recipients.append((department_emails[department], f"{department.title()} Department"))

    # Send notifications to all recipients
    for recipient_email, recipient_name in all_recipients:
        subject = f"New Hr Document Uploaded - {files[0]['filename'] if files else batch_name}"
        body = f"""
        <html>
            <body>
                <h2>📄 New Document Uploaded for Review</h2>
                <p><strong>📋 Document:</strong> {files[0]['filename'] if files else batch_name}</p>
                <p><strong>👤 Uploaded by:</strong> {uploader['full_name']} ({uploader['email']})</p>
                <p><strong>🏢 From Department:</strong> {uploader['department'].title()}</p>
                <p><strong>🎯 Target Department:</strong> {department.title()}</p>
                <p><strong>📊 Batch Name:</strong> {batch_name}</p>
                <p><strong>📁 Number of Files:</strong> {len(files)}</p>

                <h3>📋 File Details:</h3>
                <ul>
        """

        for file in files:
            body += f"<li>📄 {file['filename']} - Type: {file['type']}, Priority: {file['priority']}</li>"

        body += f"""
                </ul>

                <p><strong>🎯 Action Required:</strong> Please review these documents in the IDCR system.</p>
                <p><strong>⏰ Uploaded at:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

                <hr>
                <p style="font-size: 12px; color: #666;">
                    This is an automated notification from the IDCR Document Management System.
                </p>
            </body>
        </html>
        """

        await send_email_demo(recipient_email, subject, body, "document_notification")

@app.get("/api/documents")
async def get_documents(current_user: dict = Depends(get_current_user)):
    conn = sqlite3.connect('idcr_documents.db')
    cursor = conn.cursor()

    if current_user['role'] in ['manager', 'admin']:
        # Managers can see ALL documents for their department (regardless of who uploaded)
        cursor.execute('''
            SELECT d.*, u.full_name as uploader_name
            FROM documents d
            JOIN users u ON d.uploaded_by = u.id
            WHERE d.target_department = ? OR d.document_type = ?
            ORDER BY d.uploaded_at DESC
        ''', (current_user['department'], current_user['department']))
    else:
        # Employees can only see their own documents
        cursor.execute('''
            SELECT d.*, u.full_name as uploader_name
            FROM documents d
            JOIN users u ON d.uploaded_by = u.id
            WHERE d.uploaded_by = ?
            ORDER BY d.uploaded_at DESC
        ''', (current_user['id'],))

    documents = cursor.fetchall()
    conn.close()

    return {
        "documents": [
            {
                "doc_id": doc[1],
                "original_name": doc[4],
                "document_type": doc[9],
                "priority": doc[10],
                "review_status": doc[11],
                "uploaded_at": doc[12],
                "department": doc[8],
                "uploader": doc[-1]
            }
            for doc in documents
        ]
    }

@app.get("/api/stats")
async def get_statistics(current_user: dict = Depends(get_current_user)):
    conn = sqlite3.connect('idcr_documents.db')
    cursor = conn.cursor()

    # Basic statistics
    if current_user['role'] in ['manager', 'admin']:
        # Managers see stats for their department
        cursor.execute('SELECT COUNT(*) FROM documents WHERE target_department = ? OR document_type = ?', 
                      (current_user['department'], current_user['department']))
        total_docs = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM documents WHERE (target_department = ? OR document_type = ?) AND review_status = "approved"',
                      (current_user['department'], current_user['department']))
        processed_docs = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM documents WHERE (target_department = ? OR document_type = ?) AND review_status = "pending"',
                      (current_user['department'], current_user['department']))
        pending_docs = cursor.fetchone()[0]
    else:
        # Employees see their own stats
        cursor.execute('SELECT COUNT(*) FROM documents WHERE uploaded_by = ?', (current_user['id'],))
        total_docs = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM documents WHERE uploaded_by = ? AND review_status = "approved"', (current_user['id'],))
        processed_docs = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM documents WHERE uploaded_by = ? AND review_status = "pending"', (current_user['id'],))
        pending_docs = cursor.fetchone()[0]

    processing_rate = round((processed_docs / total_docs * 100) if total_docs > 0 else 0, 1)

    conn.close()

    return {
        "total_documents": total_docs,
        "processed_documents": processed_docs,
        "pending_documents": pending_docs,
        "processing_rate": processing_rate,
        "document_types": {},
        "departments": {},
        "priorities": {},
        "upload_trends": []
    }

@app.get("/api/email-notifications")
async def get_email_notifications(current_user: dict = Depends(get_current_user)):
    conn = sqlite3.connect('idcr_documents.db')
    cursor = conn.cursor()

    if current_user['role'] in ['manager', 'admin']:
        # Managers see notifications for their department
        department_emails = {
            'hr': 'hr@company.com',
            'finance': 'finance@company.com', 
            'legal': 'legal@company.com',
            'it': 'it@company.com',
            'operations': 'operations@company.com'
        }

        dept_email = department_emails.get(current_user['department'], '')
        cursor.execute('''
            SELECT * FROM email_notifications 
            WHERE recipient_email = ? OR recipient_email LIKE ?
            ORDER BY sent_at DESC
            LIMIT 50
        ''', (dept_email, f"%{current_user['department']}%"))
    else:
        # Employees see their own notifications
        cursor.execute('''
            SELECT * FROM email_notifications 
            WHERE recipient_email = ?
            ORDER BY sent_at DESC
            LIMIT 50
        ''', (current_user['email'],))

    emails = cursor.fetchall()
    conn.close()

    return {
        "emails": [
            {
                "id": email[0],
                "recipient": email[1],
                "subject": email[2],
                "type": email[5],
                "sent_at": email[4]
            }
            for email in emails
        ]
    }

@app.post("/api/documents/{doc_id}/review")
async def review_document(
    doc_id: str,
    action: str = Form(...),
    comments: str = Form(""),
    current_user: dict = Depends(get_current_user)
):
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Only managers can review documents")

    conn = sqlite3.connect('idcr_documents.db')
    cursor = conn.cursor()

    # Update document status
    cursor.execute('''
        UPDATE documents 
        SET review_status = ?, reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?
        WHERE doc_id = ?
    ''', (action, current_user['id'], doc_id))

    # Get document details for notification
    cursor.execute('''
        SELECT d.original_name, d.uploaded_by, u.email, u.full_name
        FROM documents d
        JOIN users u ON d.uploaded_by = u.id
        WHERE d.doc_id = ?
    ''', (doc_id,))

    doc_info = cursor.fetchone()
    conn.commit()
    conn.close()

    if doc_info:
        # Send notification to document uploader
        subject = f"Document Review: {doc_info[0]} - {action.title()}"
        body = f"""
        <h2>Document Review Complete</h2>
        <p>Hello {doc_info[3]},</p>
        <p>Your document <strong>{doc_info[0]}</strong> has been <strong>{action}</strong> by {current_user['full_name']}.</p>
        {f'<p><strong>Comments:</strong> {comments}</p>' if comments else ''}
        <p>Please check the IDCR system for more details.</p>
        """

        await send_email_demo(doc_info[2], subject, body, "document_review")

    return {"message": f"Document {action} successfully", "doc_id": doc_id}

# Mount static files and serve frontend
app.mount("/static", StaticFiles(directory="Final-project_training"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    try:
        with open("Final-project_training/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Frontend not found</h1>")

if __name__ == "__main__":
    import uvicorn

    # Initialize database
    init_database()

    print("🚀 Starting IDCR Demo Server...")
    print("📂 Frontend available at: http://0.0.0.0:5000")
    print("📊 API docs available at: http://0.0.0.0:5000/docs")

    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")