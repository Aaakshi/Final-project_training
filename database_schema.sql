
-- IDCR System Database Schema
-- Complete Entity-Relationship Implementation

-- Users table for authentication and role management
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'manager', 'employee', 'general')),
    department VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Departments configuration table
CREATE TABLE departments (
    dept_id VARCHAR(50) PRIMARY KEY,
    dept_name VARCHAR(100) NOT NULL,
    manager_email VARCHAR(255),
    classification_keywords TEXT, -- JSON format
    default_priority VARCHAR(20) DEFAULT 'medium',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Upload batches for tracking batch uploads
CREATE TABLE upload_batches (
    batch_id VARCHAR(36) PRIMARY KEY,
    batch_name VARCHAR(255),
    total_files INTEGER NOT NULL,
    processed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed'))
);

-- Main documents table
CREATE TABLE documents (
    doc_id VARCHAR(36) PRIMARY KEY,
    original_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by VARCHAR(50) REFERENCES users(user_id),
    processing_status VARCHAR(50) DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed', 'error')),
    extracted_text TEXT,
    ocr_confidence FLOAT,
    document_type VARCHAR(100),
    department VARCHAR(100) REFERENCES departments(dept_id),
    priority VARCHAR(50) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    classification_confidence FLOAT,
    page_count INTEGER,
    language VARCHAR(10),
    tags TEXT, -- JSON format
    batch_id VARCHAR(36) REFERENCES upload_batches(batch_id)
);

-- Processing logs for audit trail
CREATE TABLE processing_logs (
    log_id VARCHAR(36) PRIMARY KEY,
    doc_id VARCHAR(36) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    processing_step VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT, -- JSON format
    error_message TEXT
);

-- Email notifications tracking
CREATE TABLE email_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_email VARCHAR(255) NOT NULL,
    to_email VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    body_html TEXT,
    notification_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    doc_id VARCHAR(36) REFERENCES documents(doc_id),
    user_id VARCHAR(50) REFERENCES users(user_id),
    error_message TEXT
);

-- Document reviews for approval workflow
CREATE TABLE document_reviews (
    review_id VARCHAR(36) PRIMARY KEY,
    doc_id VARCHAR(36) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    reviewer_id VARCHAR(50) NOT NULL REFERENCES users(user_id),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'needs_revision')),
    comments TEXT,
    reviewed_at TIMESTAMP,
    decision VARCHAR(50),
    metadata TEXT, -- JSON format
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Routing rules for document classification
CREATE TABLE routing_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition TEXT NOT NULL, -- JSON format
    assignee VARCHAR(100),
    priority INTEGER,
    department VARCHAR(100) REFERENCES departments(dept_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- User sessions for JWT management
CREATE TABLE user_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    jwt_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- Audit logs for security and compliance
CREATE TABLE audit_logs (
    audit_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    old_values TEXT, -- JSON format
    new_values TEXT, -- JSON format
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- Indexes for performance optimization
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX idx_documents_department ON documents(department);
CREATE INDEX idx_documents_status ON documents(processing_status);
CREATE INDEX idx_documents_uploaded_at ON documents(uploaded_at);
CREATE INDEX idx_processing_logs_doc_id ON processing_logs(doc_id);
CREATE INDEX idx_processing_logs_timestamp ON processing_logs(timestamp);
CREATE INDEX idx_email_notifications_doc_id ON email_notifications(doc_id);
CREATE INDEX idx_email_notifications_user_id ON email_notifications(user_id);
CREATE INDEX idx_email_notifications_status ON email_notifications(status);
CREATE INDEX idx_document_reviews_doc_id ON document_reviews(doc_id);
CREATE INDEX idx_document_reviews_reviewer_id ON document_reviews(reviewer_id);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);

-- Insert default departments
INSERT INTO departments (dept_id, dept_name, manager_email, default_priority) VALUES
('hr', 'Human Resources', 'hr.manager@company.com', 'medium'),
('finance', 'Finance', 'finance.manager@company.com', 'high'),
('legal', 'Legal', 'legal.manager@company.com', 'high'),
('it', 'Information Technology', 'it.manager@company.com', 'medium'),
('operations', 'Operations', 'operations.manager@company.com', 'medium'),
('support', 'Customer Support', 'support.manager@company.com', 'medium'),
('procurement', 'Procurement', 'procurement.manager@company.com', 'medium'),
('marketing', 'Marketing', 'marketing.manager@company.com', 'low'),
('sales', 'Sales', 'sales.manager@company.com', 'medium'),
('general', 'General', 'general.manager@company.com', 'low');

-- Insert default users
INSERT INTO users (user_id, username, email, password_hash, role, department) VALUES
('admin', 'admin', 'admin@company.com', 'hashed_password', 'admin', 'it'),
('hr_manager', 'hr.manager', 'hr.manager@company.com', 'hashed_password', 'manager', 'hr'),
('finance_manager', 'finance.manager', 'finance.manager@company.com', 'hashed_password', 'manager', 'finance'),
('legal_manager', 'legal.manager', 'legal.manager@company.com', 'hashed_password', 'manager', 'legal'),
('general_employee', 'general.employee', 'general.employee@company.com', 'hashed_password', 'employee', 'general');

-- Insert default routing rules
INSERT INTO routing_rules (condition, assignee, priority, department) VALUES
('{"keywords": ["invoice", "payment", "receipt"]}', 'finance.manager@company.com', 1, 'finance'),
('{"keywords": ["contract", "agreement", "legal"]}', 'legal.manager@company.com', 1, 'legal'),
('{"keywords": ["employee", "hr", "policy"]}', 'hr.manager@company.com', 1, 'hr'),
('{"keywords": ["technical", "it", "system"]}', 'it.manager@company.com', 1, 'it');
