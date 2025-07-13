
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
import sqlite3
import uuid
import datetime
import os
import hashlib
import jwt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import PyPDF2
import docx
from werkzeug.utils import secure_filename
import uvicorn

# Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
DB_PATH = "idcr_documents.db"

app = FastAPI(title="IDCR System")
security = HTTPBearer()

# Email configuration
EMAIL_CONFIG = {
    'smtp_server': 'smtp-mail.outlook.com',
    'smtp_port': 587,
    'sender_email': 'your-email@outlook.com',
    'sender_password': 'your-app-password'
}

def send_email(to_email, subject, body, cc_email=None, bcc_email=None, reply_to=None):
    """Send email notification"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if cc_email:
            msg['Cc'] = cc_email
        if reply_to:
            msg['Reply-To'] = reply_to

        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        
        recipients = [to_email]
        if cc_email:
            recipients.append(cc_email)
        if bcc_email:
            recipients.append(bcc_email)
            
        server.sendmail(EMAIL_CONFIG['sender_email'], recipients, msg.as_string())
        server.quit()
        
        print(f"✅ Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {e}")
        return False

def init_database():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(50) PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(255) NOT NULL,
            department VARCHAR(100) NOT NULL,
            role VARCHAR(50) DEFAULT 'employee' CHECK (role IN ('employee', 'manager', 'admin')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # Create documents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            doc_id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL REFERENCES users(user_id),
            original_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_size INTEGER NOT NULL,
            file_type VARCHAR(50) NOT NULL,
            mime_type VARCHAR(100),
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processing_status VARCHAR(50) DEFAULT 'uploaded' CHECK (processing_status IN ('uploaded', 'processing', 'classified', 'routed', 'reviewed', 'archived')),
            extracted_text TEXT,
            document_type VARCHAR(100),
            department VARCHAR(100),
            priority VARCHAR(50) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
            classification_confidence REAL,
            page_count INTEGER,
            language VARCHAR(10) DEFAULT 'en',
            tags TEXT,
            review_status VARCHAR(50) DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected', 'needs_revision'))
        )
    ''')
    
    # Create upload_batches table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS upload_batches (
            batch_id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL REFERENCES users(user_id),
            batch_name VARCHAR(255) NOT NULL,
            total_files INTEGER NOT NULL,
            processed_files INTEGER DEFAULT 0,
            failed_files INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status VARCHAR(50) DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed'))
        )
    ''')
    
    # Create document_reviews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_reviews (
            review_id VARCHAR(36) PRIMARY KEY,
            doc_id VARCHAR(36) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
            reviewer_id VARCHAR(50) NOT NULL REFERENCES users(user_id),
            status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'needs_revision')),
            comments TEXT,
            reviewed_at TIMESTAMP,
            decision VARCHAR(50),
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return {
            "user_id": user[0],
            "email": user[1],
            "full_name": user[3],
            "department": user[4],
            "role": user[5]
        }
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/", response_class=HTMLResponse)
async def get_frontend():
    """Serve the main frontend"""
    try:
        with open("Final-project_training/index.html", "r") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Frontend file not found</h1>", status_code=404)

@app.post("/api/register")
async def register(request: Request):
    """Register a new user"""
    data = await request.json()
    email = data.get("email")
    password = data.get("password")
    full_name = data.get("full_name")
    department = data.get("department")
    
    if not all([email, password, full_name, department]):
        raise HTTPException(status_code=400, detail="All fields are required")
    
    user_id = str(uuid.uuid4())
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (user_id, email, password_hash, full_name, department)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, email, password_hash, full_name, department))
        conn.commit()
        conn.close()
        
        return {"message": "User registered successfully", "user_id": user_id}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists")

@app.post("/api/login")
async def login(request: Request):
    """Login user and return JWT token"""
    data = await request.json()
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ? AND password_hash = ?", (email, password_hash))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token_data = {"sub": user[0]}
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    
    return {
        "access_token": token,
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
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@app.post("/api/bulk-upload")
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

@app.get("/api/documents")
async def get_documents(
    department: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get documents with optional filtering"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = "SELECT * FROM documents WHERE 1=1"
    params = []
    
    # Filter by department if user is manager/admin
    if current_user['role'] in ['manager', 'admin']:
        if department:
            query += " AND department = ?"
            params.append(department)
        elif current_user['role'] == 'manager':
            query += " AND department = ?"
            params.append(current_user['department'])
    else:
        # Regular employees see only their documents
        query += " AND user_id = ?"
        params.append(current_user['user_id'])
    
    if status:
        query += " AND processing_status = ?"
        params.append(status)
    
    query += " ORDER BY uploaded_at DESC"
    
    cursor.execute(query, params)
    documents = cursor.fetchall()
    conn.close()
    
    return {"documents": [dict(zip([col[0] for col in cursor.description], doc)) for doc in documents]}

@app.get("/api/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Get dashboard statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total documents
    cursor.execute("SELECT COUNT(*) FROM documents")
    total_docs = cursor.fetchone()[0]
    
    # Processed documents
    cursor.execute("SELECT COUNT(*) FROM documents WHERE processing_status = 'classified'")
    processed_docs = cursor.fetchone()[0]
    
    # Pending documents
    cursor.execute("SELECT COUNT(*) FROM documents WHERE review_status = 'pending'")
    pending_docs = cursor.fetchone()[0]
    
    # Error documents
    cursor.execute("SELECT COUNT(*) FROM documents WHERE processing_status = 'failed'")
    error_docs = cursor.fetchone()[0]
    
    # Processing rate
    processing_rate = (processed_docs / total_docs * 100) if total_docs > 0 else 0
    
    # Documents by department
    cursor.execute("SELECT department, COUNT(*) FROM documents GROUP BY department")
    dept_stats = dict(cursor.fetchall())
    
    # Document types
    cursor.execute("SELECT document_type, COUNT(*) FROM documents GROUP BY document_type")
    doc_types = dict(cursor.fetchall())
    
    # Priorities
    cursor.execute("SELECT priority, COUNT(*) FROM documents GROUP BY priority")
    priorities = dict(cursor.fetchall())
    
    # Upload trends (last 30 days)
    cursor.execute("""
        SELECT DATE(uploaded_at) as date, COUNT(*) as count 
        FROM documents 
        WHERE uploaded_at >= datetime('now', '-30 days')
        GROUP BY DATE(uploaded_at)
        ORDER BY date
    """)
    upload_trends = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "total_documents": total_docs,
        "processed_documents": processed_docs,
        "pending_documents": pending_docs,
        "error_documents": error_docs,
        "processing_rate": round(processing_rate, 1),
        "department_stats": dept_stats,
        "document_types": doc_types,
        "departments": dept_stats,
        "priorities": priorities,
        "upload_trends": upload_trends
    }

@app.get("/api/documents/{doc_id}")
async def get_document_details(
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed information about a document"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
    doc = cursor.fetchone()
    
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get column names
    column_names = [description[0] for description in cursor.description]
    doc_dict = dict(zip(column_names, doc))
    
    # Get review information if available
    cursor.execute("""
        SELECT dr.*, u.full_name as reviewer_name 
        FROM document_reviews dr
        LEFT JOIN users u ON dr.reviewer_id = u.user_id
        WHERE dr.doc_id = ?
        ORDER BY dr.reviewed_at DESC
        LIMIT 1
    """, (doc_id,))
    review = cursor.fetchone()
    
    if review:
        doc_dict['reviewed_by'] = review[8]  # reviewer_name
        doc_dict['reviewed_at'] = review[6]  # reviewed_at
        doc_dict['review_comments'] = review[4]  # comments
    
    conn.close()
    return doc_dict

@app.get("/api/email-notifications")
async def get_email_notifications(
    page: int = 1,
    page_size: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get email notifications (simulated)"""
    # This is a demo endpoint that simulates email notifications
    # In a real system, this would fetch from an email logs table
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get recent documents for email simulation
    cursor.execute("""
        SELECT d.*, u.full_name as uploader_name, u.email as uploader_email
        FROM documents d
        LEFT JOIN users u ON d.user_id = u.user_id
        WHERE d.department = ? OR d.user_id = ?
        ORDER BY d.uploaded_at DESC
        LIMIT ?
    """, (current_user['department'], current_user['user_id'], page_size))
    
    documents = cursor.fetchall()
    conn.close()
    
    # Simulate email notifications
    emails = []
    for doc in documents:
        # Notification to department manager
        if current_user['role'] in ['manager', 'admin']:
            emails.append({
                "subject": f"New Document Uploaded: {doc[2]}",
                "sent_by": "noreply@idcr-system.com",
                "sent_by_name": "IDCR System",
                "received_by": f"{current_user['department']}.manager@company.com",
                "received_by_name": f"{current_user['department'].title()} Manager",
                "sent_at": doc[7],
                "email_type": "received",
                "status": "delivered",
                "document_name": doc[2],
                "document_type": doc[10] or "General",
                "department": doc[11] or "General",
                "priority": doc[12] or "Medium",
                "body_preview": f"A new document has been uploaded and requires review..."
            })
        
        # Confirmation to uploader
        if doc[1] == current_user['user_id']:
            emails.append({
                "subject": f"Document Upload Confirmation: {doc[2]}",
                "sent_by": "noreply@idcr-system.com", 
                "sent_by_name": "IDCR System",
                "received_by": current_user['email'],
                "received_by_name": current_user['full_name'],
                "sent_at": doc[7],
                "email_type": "received",
                "status": "delivered",
                "document_name": doc[2],
                "document_type": doc[10] or "General",
                "department": doc[11] or "General",
                "priority": doc[12] or "Medium",
                "body_preview": f"Your document has been successfully uploaded and sent for review..."
            })
    
    return {"emails": emails[:page_size]}

@app.post("/api/documents/{doc_id}/review")
async def review_document(
    doc_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Review a document (approve/reject)"""
    data = await request.json()
    status = data.get("status")
    comments = data.get("comments", "")
    
    if status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get document details for notification
    cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
    doc = cursor.fetchone()
    
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Update document review status
    cursor.execute('''
        UPDATE documents 
        SET review_status = ?, processing_status = ?
        WHERE doc_id = ?
    ''', (status, "reviewed", doc_id))
    
    # Create review record
    review_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO document_reviews (review_id, doc_id, reviewer_id, status, comments, reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (review_id, doc_id, current_user['user_id'], status, comments, datetime.datetime.utcnow().isoformat()))
    
    # Get uploader details for notification
    cursor.execute("SELECT email, full_name FROM users WHERE user_id = ?", (doc[1],))
    uploader = cursor.fetchone()
    
    conn.commit()
    conn.close()
    
    # Send notification email to document uploader
    if uploader:
        subject = f"Document Review Complete: {doc[2]} - {status.upper()}"
        body = f"""
        <html>
            <body>
                <h2>Document Review Update</h2>
                <p>Dear {uploader[1]},</p>
                <p>Your document <strong>{doc[2]}</strong> has been <strong>{status}</strong> by {current_user['full_name']}.</p>
                
                <h3>Review Details:</h3>
                <ul>
                    <li><strong>Document:</strong> {doc[2]}</li>
                    <li><strong>Status:</strong> {status.upper()}</li>
                    <li><strong>Reviewed by:</strong> {current_user['full_name']} ({current_user['department'].upper()} Department)</li>
                    <li><strong>Date:</strong> {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}</li>
                    {f'<li><strong>Comments:</strong> {comments}</li>' if comments else ''}
                </ul>
                
                <p>You can view the full details in the IDCR system.</p>
                <p>Best regards,<br>IDCR System</p>
            </body>
        </html>
        """
        
        send_email(uploader[0], subject, body, None, None, current_user['email'])
    
    return {"message": f"Document {status} successfully"}

if __name__ == "__main__":
    init_database()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
