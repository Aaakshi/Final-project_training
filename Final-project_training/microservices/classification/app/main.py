
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
import re
import time
import io
import PyPDF2
import docx
import pandas as pd
from PIL import Image
import pytesseract
import openpyxl

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from libs.utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

app = FastAPI(title="Advanced Classification Service")

class ClassificationResult(BaseModel):
    doc_type: str
    department: str
    priority: str
    confidence: float
    extracted_text: str
    page_count: int
    language: str = "en"
    tags: List[str] = []
    ocr_confidence: Optional[float] = None

class BulkClassificationResponse(BaseModel):
    batch_id: str
    total_files: int
    processed_files: int
    results: List[ClassificationResult]

# Comprehensive Department Classification (12 Departments as per guide)
DEPARTMENT_PATTERNS = {
    'hr': [
        # HR Keywords from guide
        r'employee\s*id', r'hiring', r'appraisal', r'benefits', r'recruitment', 
        r'onboarding', r'resignation', r'pto', r'attendance', r'hr\s*policy',
        r'human\s*resources', r'payroll', r'performance\s*review', r'training',
        r'personnel', r'leave\s*application', r'offer\s*letter', r'appointment\s*letter',
        r'resume', r'cv', r'salary', r'employee', r'staff'
    ],
    'finance': [
        # Finance & Accounting Keywords from guide
        r'invoice', r'payment', r'accounts\s*payable', r'ledger', r'tax', 
        r'balance\s*sheet', r'fiscal', r'payroll', r'expenses', r'revenue', 
        r'debit', r'credit', r'accounting', r'budget', r'financial', r'profit',
        r'loss', r'audit', r'receipt', r'billing', r'cost', r'amount\s*due'
    ],
    'legal': [
        # Legal Keywords from guide
        r'non[\-\s]*disclosure', r'contract', r'agreement', r'terms', r'regulation',
        r'compliance', r'clause', r'legal', r'dispute', r'jurisdiction', r'breach',
        r'nda', r'mou', r'policy', r'lawsuit', r'attorney', r'litigation',
        r'whereas', r'witnesseth', r'consideration', r'covenant'
    ],
    'sales': [
        # Sales Keywords from guide
        r'sales\s*target', r'lead', r'quotation', r'conversion', r'pipeline',
        r'customer', r'deal', r'revenue', r'proposal', r'client', r'crm',
        r'sales\s*report', r'prospect', r'commission', r'territory'
    ],
    'marketing': [
        # Marketing Keywords from guide
        r'campaign', r'branding', r'seo', r'email\s*blast', r'content', 
        r'engagement', r'target\s*audience', r'lead\s*generation', r'ad\s*spend',
        r'marketing', r'promotion', r'advertising', r'brand', r'social\s*media',
        r'event\s*planning'
    ],
    'it': [
        # IT Keywords from guide
        r'server', r'network', r'incident', r'troubleshooting', r'firewall',
        r'access\s*control', r'login', r'cybersecurity', r'sla', r'it\s*support',
        r'technology', r'software', r'hardware', r'system', r'database',
        r'security', r'application', r'user\s*guide', r'system\s*log'
    ],
    'operations': [
        # Operations Keywords from guide
        r'logistics', r'supply', r'workflow', r'daily\s*operations', r'sop',
        r'inventory', r'maintenance', r'efficiency', r'process', r'procedure',
        r'production', r'supply\s*chain', r'standard\s*operating\s*procedure'
    ],
    'customer_support': [
        # Customer Support Keywords from guide
        r'ticket', r'customer\s*issue', r'response\s*time', r'escalation',
        r'helpdesk', r'satisfaction', r'support\s*team', r'client\s*query',
        r'chat\s*log', r'feedback', r'service\s*report', r'help\s*desk'
    ],
    'procurement': [
        # Procurement/Purchase Keywords from guide
        r'purchase\s*order', r'vendor', r'quotation', r'invoice', r'rfq',
        r'delivery', r'procure', r'supplier', r'inventory', r'vendor\s*agreement',
        r'bill', r'delivery\s*note', r'purchase', r'po\s*#', r'requisition'
    ],
    'product': [
        # Product/R&D Keywords from guide
        r'feature', r'testing', r'prototype', r'bug', r'release', r'version',
        r'specification', r'roadmap', r'r&d', r'research', r'development',
        r'product\s*spec', r'design\s*doc', r'bug\s*report', r'test\s*report'
    ],
    'administration': [
        # Administration Keywords from guide
        r'facility', r'stationery', r'asset', r'building\s*maintenance', r'admin',
        r'general\s*request', r'supplies', r'office\s*supplies', r'asset\s*allocation',
        r'general\s*notice', r'administrative'
    ],
    'executive': [
        # Executive/Management Keywords from guide
        r'strategy', r'kpi', r'vision', r'mission', r'goals', r'board', r'agenda',
        r'quarterly\s*review', r'annual\s*report', r'management', r'executive',
        r'strategic', r'board\s*meeting', r'vision\s*statement'
    ]
}

# Comprehensive Priority Classification (as per guide)
PRIORITY_PATTERNS = {
    'high': [
        # Deadlines (High Priority)
        r'by\s*eod', r'by\s*end\s*of\s*day', r'by\s*today', r'asap', r'urgent',
        r'immediate', r'within\s*24\s*hours', r'deadline\s*today', r'due\s*today',
        r'respond\s*by', r'reply\s*immediately',
        # Action Requests (High Priority)
        r'action\s*required', r'requires\s*immediate\s*attention', 
        r'please\s*review\s*urgently', r'high\s*priority', r'critical\s*issue',
        r'resolve\s*now',
        # Escalations/Issues (High Priority)
        r'escalated', r'service\s*disruption', r'breach', r'incident',
        r'system\s*down', r'customer\s*complaint', r'payment\s*failed',
        # Meetings/Events (High Priority)
        r'today\'s\s*meeting', r'final\s*review', r'must\s*attend',
        r'confirmation\s*needed', r'emergency', r'critical'
    ],
    'medium': [
        # Follow-ups (Medium Priority)
        r'reminder', r'follow\s*up', r'this\s*week', r'pending', 
        r'awaiting\s*response', r'check\s*status', r'update\s*needed',
        # Upcoming Deadlines (Medium Priority)
        r'by\s*tomorrow', r'due\s*in\s*2\s*days', r'schedule\s*by',
        r'before\s*friday', r'complete\s*by', r'eta',
        # Meetings (Medium Priority)
        r'scheduled\s*for', r'calendar\s*invite', r'tentative',
        r'planned\s*discussion', r'agenda',
        # Tasks (Medium Priority)
        r'work\s*in\s*progress', r'assigned', r'need\s*update',
        r'submit\s*by', r'to\s*be\s*reviewed', r'important', r'moderate',
        r'standard', r'normal', r'regular'
    ],
    'low': [
        # FYI/Reference (Low Priority)
        r'for\s*your\s*information', r'no\s*action\s*needed', r'for\s*record',
        r'just\s*sharing', r'reference\s*document', r'read\s*only', r'optional',
        # Long-Term (Low Priority)
        r'next\s*quarter', r'next\s*month', r'future\s*release', r'roadmap',
        r'tentative\s*plan', r'long[\-\s]*term\s*goal', r'backlog\s*item',
        # General Updates (Low Priority)
        r'weekly\s*summary', r'monthly\s*report', r'feedback',
        r'draft\s*version', r'notes', r'not\s*urgent', r'low\s*priority',
        r'when\s*convenient', r'no\s*rush', r'informational', r'fyi'
    ]
}

# Enhanced Document Type Patterns
DOCUMENT_TYPE_PATTERNS = {
    'invoice': [r'invoice', r'bill', r'amount\s*due', r'total\s*amount', r'payment\s*due', r'inv\s*#', r'billing'],
    'contract': [r'contract', r'agreement', r'terms\s*and\s*conditions', r'parties\s*agree', r'whereas', r'witnesseth'],
    'purchase_order': [r'purchase\s*order', r'po\s*#', r'order\s*number', r'vendor', r'ship\s*to', r'bill\s*to'],
    'receipt': [r'receipt', r'paid', r'transaction', r'thank\s*you\s*for\s*your\s*purchase', r'payment\s*received'],
    'report': [r'report', r'analysis', r'summary', r'findings', r'recommendations', r'executive\s*summary'],
    'memo': [r'memorandum', r'memo', r'to:', r'from:', r'subject:', r'date:'],
    'letter': [r'dear', r'sincerely', r'regards', r'yours\s*truly', r'correspondence'],
    'resume': [r'resume', r'cv', r'curriculum\s*vitae', r'experience', r'education', r'skills'],
    'policy': [r'policy', r'guideline', r'procedure', r'standard', r'regulation'],
    'specification': [r'specification', r'spec', r'requirement', r'feature', r'technical\s*doc']
}

def extract_text_from_file(content: bytes, filename: str, content_type: str) -> tuple[str, int]:
    """Enhanced text extraction with OCR support"""
    text = ""
    page_count = 1
    
    try:
        if content_type == 'application/pdf':
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            page_count = len(pdf_reader.pages)
            
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            # If no text extracted, try OCR
            if not text.strip():
                try:
                    # Convert PDF to images and OCR
                    import fitz  # PyMuPDF
                    doc = fitz.open(stream=content, filetype="pdf")
                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)
                        pix = page.get_pixmap()
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        ocr_text = pytesseract.image_to_string(img)
                        text += ocr_text + "\n"
                except Exception as e:
                    logger.warning(f"OCR failed for PDF: {e}")
                    
        elif content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            doc = docx.Document(io.BytesIO(content))
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
                
        elif content_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            df = pd.read_excel(io.BytesIO(content))
            text = df.to_string()
            
        elif content_type == 'text/plain':
            text = content.decode('utf-8', errors='ignore')
            
        elif content_type in ['image/jpeg', 'image/png', 'image/tiff']:
            # OCR for images
            img = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(img)
            
        else:
            # Try to decode as text
            text = content.decode('utf-8', errors='ignore')
            
    except Exception as e:
        logger.error(f"Text extraction failed for {filename}: {e}")
        text = ""
    
    return text.strip(), page_count

def classify_document_type(text: str) -> tuple[str, float]:
    """Classify document type with confidence scoring"""
    text_lower = text.lower()
    scores = {}
    
    for doc_type, patterns in DOCUMENT_TYPE_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = len(re.findall(pattern, text_lower))
            score += matches * 2  # Weight document type patterns more
        scores[doc_type] = score
    
    if not scores or max(scores.values()) == 0:
        return "document", 0.5
    
    best_type = max(scores, key=scores.get)
    max_score = scores[best_type]
    confidence = min(0.95, 0.3 + (max_score * 0.1))
    
    return best_type, confidence

def classify_department(text: str) -> tuple[str, float]:
    """Enhanced department classification with all 12 departments"""
    text_lower = text.lower()
    scores = {}
    
    for dept, patterns in DEPARTMENT_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = len(re.findall(pattern, text_lower))
            score += matches
        scores[dept] = score
    
    if not scores or max(scores.values()) == 0:
        return "general", 0.5
    
    best_dept = max(scores, key=scores.get)
    max_score = scores[best_dept]
    confidence = min(0.95, 0.4 + (max_score * 0.08))
    
    return best_dept, confidence

def classify_priority(text: str) -> tuple[str, float]:
    """Enhanced priority classification based on comprehensive patterns"""
    text_lower = text.lower()
    scores = {}
    
    for priority, patterns in PRIORITY_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = len(re.findall(pattern, text_lower))
            # Weight high priority indicators more heavily
            weight = 3 if priority == 'high' else 2 if priority == 'medium' else 1
            score += matches * weight
        scores[priority] = score
    
    if not scores or max(scores.values()) == 0:
        return "medium", 0.5
    
    best_priority = max(scores, key=scores.get)
    max_score = scores[best_priority]
    confidence = min(0.95, 0.5 + (max_score * 0.08))
    
    return best_priority, confidence

def extract_advanced_tags(text: str) -> List[str]:
    """Extract comprehensive tags from document content"""
    tags = []
    text_lower = text.lower()
    
    # Business status terms
    status_terms = [
        'confidential', 'urgent', 'draft', 'final', 'approved', 'pending', 
        'completed', 'cancelled', 'revised', 'classified', 'sensitive'
    ]
    
    for term in status_terms:
        if term in text_lower:
            tags.append(term)
    
    # Financial indicators
    if re.search(r'\$[\d,]+|\€[\d,]+|£[\d,]+', text):
        tags.append('financial')
    
    # Date indicators
    if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text):
        tags.append('dated')
    
    # Contract/Legal indicators
    if re.search(r'signature|sign|executed|effective\s*date', text_lower):
        tags.append('executable')
    
    # Technical indicators
    if re.search(r'api|database|server|network|software', text_lower):
        tags.append('technical')
    
    # Meeting/Event indicators
    if re.search(r'meeting|conference|presentation|workshop', text_lower):
        tags.append('meeting')
    
    return tags[:8]  # Limit to 8 tags

def detect_language(text: str) -> str:
    """Simple language detection"""
    # Basic language detection - can be enhanced with proper language detection libraries
    common_english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
    text_lower = text.lower()
    
    english_word_count = sum(1 for word in common_english_words if word in text_lower)
    if english_word_count >= 3:
        return "en"
    
    return "unknown"

@app.post("/classify", response_model=ClassificationResult)
async def classify_document(file: UploadFile = File(...)):
    """Advanced document classification with comprehensive feature set"""
    try:
        content = await file.read()
        
        # Extract text using enhanced OCR and other methods
        extracted_text, page_count = extract_text_from_file(
            content, file.filename, file.content_type
        )
        
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from document")
        
        # Perform comprehensive classifications
        doc_type, type_confidence = classify_document_type(extracted_text)
        department, dept_confidence = classify_department(extracted_text)
        priority, priority_confidence = classify_priority(extracted_text)
        
        # Calculate overall confidence
        overall_confidence = (type_confidence + dept_confidence + priority_confidence) / 3
        
        # Extract additional metadata
        tags = extract_advanced_tags(extracted_text)
        language = detect_language(extracted_text)
        
        result = ClassificationResult(
            doc_type=doc_type,
            department=department,
            priority=priority,
            confidence=overall_confidence,
            extracted_text=extracted_text[:2000],  # Limit for response size
            page_count=page_count,
            language=language,
            tags=tags,
            ocr_confidence=0.85 if file.content_type.startswith('image/') else None
        )
        
        logger.info(f"Classified document {file.filename}: {doc_type}/{department}/{priority} (confidence: {overall_confidence:.2f})")
        return result
        
    except Exception as e:
        logger.error(f"Classification failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@app.post("/bulk-classify", response_model=BulkClassificationResponse)
async def bulk_classify_documents(files: List[UploadFile] = File(...)):
    """Classify multiple documents in bulk with advanced processing"""
    batch_id = f"batch_{int(time.time())}"
    results = []
    processed = 0
    
    logger.info(f"Starting advanced bulk classification for {len(files)} files")
    
    for file in files:
        try:
            result = await classify_document(file)
            results.append(result)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to classify {file.filename}: {e}")
            continue
    
    return BulkClassificationResponse(
        batch_id=batch_id,
        total_files=len(files),
        processed_files=processed,
        results=results
    )

@app.get("/departments")
async def get_supported_departments():
    """Get list of all supported departments"""
    return {
        "departments": list(DEPARTMENT_PATTERNS.keys()),
        "total_count": len(DEPARTMENT_PATTERNS),
        "department_details": {
            "hr": "Human Resources",
            "finance": "Finance & Accounting", 
            "legal": "Legal",
            "sales": "Sales",
            "marketing": "Marketing",
            "it": "Information Technology",
            "operations": "Operations",
            "customer_support": "Customer Support",
            "procurement": "Procurement/Purchase",
            "product": "Product/R&D",
            "administration": "Administration",
            "executive": "Executive/Management"
        }
    }

@app.get("/priority-levels")
async def get_priority_levels():
    """Get priority level definitions"""
    return {
        "priorities": ["high", "medium", "low"],
        "definitions": {
            "high": "Time-sensitive, urgent, requires immediate action",
            "medium": "Important but not urgent - typically this week or within a few days",
            "low": "Informational, long-term, or low urgency"
        }
    }

@app.get("/ping")
async def ping():
    return {"message": "pong from Advanced Classification Service"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "features": [
            "advanced-ocr", "12-department-classification", "3-tier-priority",
            "multi-format-support", "bulk-processing", "confidence-scoring",
            "tag-extraction", "language-detection"
        ],
        "supported_formats": ["PDF", "DOCX", "TXT", "XLS/XLSX", "Images (JPG/PNG/TIFF)"],
        "departments": len(DEPARTMENT_PATTERNS),
        "version": "2.0-enhanced"
    }
