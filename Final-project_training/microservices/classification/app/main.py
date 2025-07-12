
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import sys
import os
import io
import re
from typing import List, Optional

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from libs.utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Import libraries for document processing
try:
    import pytesseract
    from PIL import Image
    import pdf2image
    from docx import Document as DocxDocument
    import pandas as pd
    import fitz  # PyMuPDF
except ImportError as e:
    logger.warning(f"Some optional dependencies not installed: {e}")

app = FastAPI(title="Enhanced Classification Service")

class ClassificationResult(BaseModel):
    doc_type: str
    department: str
    priority: str
    confidence: float
    extracted_text: str
    page_count: int
    language: str
    tags: List[str]

class BulkClassificationRequest(BaseModel):
    batch_id: str
    files: List[str]

class BulkClassificationResponse(BaseModel):
    batch_id: str
    total_files: int
    processed_files: int
    results: List[ClassificationResult]

# Document type classification rules
DOCUMENT_TYPE_PATTERNS = {
    'invoice': [
        r'invoice', r'bill', r'amount due', r'total amount', r'payment due',
        r'invoice #', r'inv\s*#', r'billing', r'charges'
    ],
    'contract': [
        r'contract', r'agreement', r'terms and conditions', r'parties agree',
        r'whereas', r'witnesseth', r'consideration', r'covenant'
    ],
    'purchase_order': [
        r'purchase order', r'po\s*#', r'order number', r'vendor',
        r'ship to', r'bill to', r'quantity', r'unit price'
    ],
    'receipt': [
        r'receipt', r'paid', r'transaction', r'thank you for your purchase',
        r'payment received', r'cashier'
    ],
    'report': [
        r'report', r'analysis', r'summary', r'findings', r'recommendations',
        r'executive summary', r'conclusion'
    ],
    'memo': [
        r'memorandum', r'memo', r'to:', r'from:', r'subject:', r'date:'
    ],
    'letter': [
        r'dear', r'sincerely', r'regards', r'yours truly', r'correspondence'
    ]
}

# Department classification rules
DEPARTMENT_PATTERNS = {
    'finance': [
        r'invoice', r'payment', r'accounting', r'budget', r'financial',
        r'revenue', r'expense', r'cost', r'profit', r'tax'
    ],
    'legal': [
        r'contract', r'agreement', r'legal', r'law', r'attorney',
        r'litigation', r'compliance', r'regulation', r'clause'
    ],
    'hr': [
        r'employee', r'hiring', r'recruitment', r'payroll', r'benefits',
        r'performance', r'training', r'personnel', r'human resources'
    ],
    'operations': [
        r'process', r'procedure', r'workflow', r'operation', r'production',
        r'logistics', r'supply chain', r'inventory'
    ],
    'marketing': [
        r'marketing', r'campaign', r'promotion', r'advertising', r'brand',
        r'customer', r'sales', r'lead', r'prospect'
    ],
    'it': [
        r'technology', r'software', r'hardware', r'system', r'network',
        r'database', r'security', r'server', r'application'
    ]
}

# Priority classification rules
PRIORITY_PATTERNS = {
    'high': [
        r'urgent', r'immediate', r'asap', r'critical', r'emergency',
        r'high priority', r'deadline', r'time sensitive'
    ],
    'medium': [
        r'important', r'moderate', r'standard', r'normal', r'regular'
    ],
    'low': [
        r'low priority', r'when convenient', r'no rush', r'informational'
    ]
}

def extract_text_from_file(file_content: bytes, filename: str, mime_type: str) -> tuple[str, int]:
    """Extract text from various file formats"""
    text = ""
    page_count = 1
    
    try:
        if mime_type == "application/pdf":
            # Use PyMuPDF for PDF text extraction
            pdf_document = fitz.open(stream=file_content, filetype="pdf")
            page_count = len(pdf_document)
            
            for page_num in range(page_count):
                page = pdf_document[page_num]
                text += page.get_text()
            
            pdf_document.close()
            
            # If no text found, try OCR
            if not text.strip():
                images = pdf2image.convert_from_bytes(file_content)
                for image in images:
                    text += pytesseract.image_to_string(image)
                    
        elif mime_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            # DOCX files
            doc = DocxDocument(io.BytesIO(file_content))
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
                
        elif mime_type in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
            # Excel files
            df = pd.read_excel(io.BytesIO(file_content))
            text = df.to_string()
            
        elif mime_type == "text/plain":
            # Plain text files
            text = file_content.decode('utf-8')
            
        elif mime_type.startswith("image/"):
            # Image files - use OCR
            image = Image.open(io.BytesIO(file_content))
            text = pytesseract.image_to_string(image)
            
    except Exception as e:
        logger.error(f"Error extracting text from {filename}: {e}")
        text = ""
    
    return text, page_count

def classify_document_type(text: str) -> tuple[str, float]:
    """Classify document type based on content"""
    text_lower = text.lower()
    scores = {}
    
    for doc_type, patterns in DOCUMENT_TYPE_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = len(re.findall(pattern, text_lower))
            score += matches
        scores[doc_type] = score
    
    if not scores or max(scores.values()) == 0:
        return "document", 0.5
    
    best_type = max(scores, key=scores.get)
    confidence = min(0.95, 0.5 + (scores[best_type] * 0.1))
    
    return best_type, confidence

def classify_department(text: str) -> tuple[str, float]:
    """Classify department based on content"""
    text_lower = text.lower()
    scores = {}
    
    for department, patterns in DEPARTMENT_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = len(re.findall(pattern, text_lower))
            score += matches
        scores[department] = score
    
    if not scores or max(scores.values()) == 0:
        return "general", 0.5
    
    best_dept = max(scores, key=scores.get)
    confidence = min(0.95, 0.5 + (scores[best_dept] * 0.1))
    
    return best_dept, confidence

def classify_priority(text: str) -> tuple[str, float]:
    """Classify priority based on content"""
    text_lower = text.lower()
    scores = {}
    
    for priority, patterns in PRIORITY_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = len(re.findall(pattern, text_lower))
            score += matches
        scores[priority] = score
    
    if not scores or max(scores.values()) == 0:
        return "medium", 0.5
    
    best_priority = max(scores, key=scores.get)
    confidence = min(0.95, 0.5 + (scores[best_priority] * 0.1))
    
    return best_priority, confidence

def extract_tags(text: str) -> List[str]:
    """Extract relevant tags from document content"""
    tags = []
    text_lower = text.lower()
    
    # Common business terms
    business_terms = [
        'confidential', 'urgent', 'draft', 'final', 'approved',
        'pending', 'completed', 'cancelled', 'revised'
    ]
    
    for term in business_terms:
        if term in text_lower:
            tags.append(term)
    
    # Extract amounts/currency
    if re.search(r'\$[\d,]+', text):
        tags.append('financial')
    
    # Extract dates
    if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text):
        tags.append('dated')
    
    return tags[:5]  # Limit to 5 tags

def detect_language(text: str) -> str:
    """Simple language detection"""
    # This is a simplified version - in production, use a proper language detection library
    if not text.strip():
        return "unknown"
    
    # Check for common English words
    english_words = ['the', 'and', 'of', 'to', 'a', 'in', 'for', 'is', 'on', 'that']
    word_count = len(text.split())
    english_count = sum(1 for word in english_words if word in text.lower())
    
    if english_count > 0 and (english_count / len(english_words)) > 0.3:
        return "en"
    
    return "unknown"

@app.post("/classify", response_model=ClassificationResult)
async def classify_document(file: UploadFile = File(...)):
    """Classify a single document with OCR and advanced classification"""
    try:
        # Read file content
        content = await file.read()
        
        # Extract text using OCR and other methods
        extracted_text, page_count = extract_text_from_file(
            content, file.filename, file.content_type
        )
        
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from document")
        
        # Perform classifications
        doc_type, type_confidence = classify_document_type(extracted_text)
        department, dept_confidence = classify_department(extracted_text)
        priority, priority_confidence = classify_priority(extracted_text)
        
        # Calculate overall confidence
        overall_confidence = (type_confidence + dept_confidence + priority_confidence) / 3
        
        # Extract additional metadata
        tags = extract_tags(extracted_text)
        language = detect_language(extracted_text)
        
        result = ClassificationResult(
            doc_type=doc_type,
            department=department,
            priority=priority,
            confidence=overall_confidence,
            extracted_text=extracted_text[:1000],  # Limit for response size
            page_count=page_count,
            language=language,
            tags=tags
        )
        
        logger.info(f"Classified document {file.filename}: {doc_type}/{department}/{priority}")
        return result
        
    except Exception as e:
        logger.error(f"Classification failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@app.post("/bulk-classify", response_model=BulkClassificationResponse)
async def bulk_classify_documents(files: List[UploadFile] = File(...)):
    """Classify multiple documents in bulk"""
    batch_id = f"batch_{int(time.time())}"
    results = []
    processed = 0
    
    logger.info(f"Starting bulk classification for {len(files)} files")
    
    for file in files:
        try:
            # Use the single file classification endpoint
            result = await classify_document(file)
            results.append(result)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to classify {file.filename}: {e}")
            # Continue with other files
            continue
    
    return BulkClassificationResponse(
        batch_id=batch_id,
        total_files=len(files),
        processed_files=processed,
        results=results
    )

@app.get("/ping")
async def ping():
    return {"message": "pong from Enhanced Classification Service"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "features": [
            "OCR", "multi-format", "bulk-processing", 
            "document-type-classification", "department-classification", 
            "priority-classification"
        ]
    }
