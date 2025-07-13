from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import sys
import os
import uvicorn

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from libs.utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

app = FastAPI(title="Classification Service")

@app.get("/")
async def root():
    return {"message": "Classification Service is running", "service": "classification"}

class ClassificationResponse(BaseModel):
    doc_type: str
    department: str
    confidence: float
    priority: str
    extracted_text: str
    page_count: int
    language: str
    tags: list

@app.post("/classify")
async def classify_document(file: UploadFile = File(...)):
    """Classify uploaded document"""
    try:
        # Read file content
        content = await file.read()
        filename = file.filename.lower()
        text_content = content.decode('utf-8', errors='ignore') if content else ""
        
        # Enhanced classification logic with comprehensive keywords
        content_lower = text_content.lower()
        
        # HR Keywords
        hr_keywords = ["hr", "human resources", "employee relations", "talent acquisition", "recruitment", 
                      "onboarding", "performance management", "compensation & benefits", "payroll", 
                      "employee engagement", "training & development", "succession planning", 
                      "workforce planning", "hr policies", "diversity & inclusion", "labor relations", 
                      "employee retention", "hris", "benefits administration", "workplace safety", 
                      "employee", "personnel", "hiring", "training", "performance", "benefits", 
                      "leave", "vacation", "sick leave", "maternity", "paternity", "disciplinary", 
                      "termination", "resignation", "promotion", "performance review", "appraisal", 
                      "job description", "organizational chart", "employee handbook", "workplace policy", 
                      "harassment", "diversity", "inclusion", "staff", "workforce", "compensation", 
                      "salary review", "performance evaluation", "employee satisfaction", "team building", 
                      "skill development", "career development"]
        
        # Finance Keywords
        finance_keywords = ["finance", "financial planning", "budgeting", "accounting", "financial reporting", 
                           "accounts payable", "accounts receivable", "general ledger", "cash flow", 
                           "profit & loss", "balance sheet", "financial analysis", "treasury", 
                           "tax compliance", "auditing", "cost management", "revenue forecasting", 
                           "capital expenditure", "financial risk management", "erp", "enterprise resource planning", 
                           "invoice", "payment", "bill", "receipt", "expense", "revenue", "profit", "loss", 
                           "tax", "audit", "salary", "wage", "reimbursement", "cost", "expenditure", 
                           "vendor payment", "purchase order", "transaction", "bank statement", "credit", "debit"]
        
        # Legal Keywords
        legal_keywords = ["legal", "compliance", "contracts", "corporate governance", "litigation", 
                         "regulatory affairs", "intellectual property", "ip", "risk management", 
                         "employment law", "data privacy", "gdpr", "general data protection regulation", 
                         "legal counsel", "dispute resolution", "due diligence", "mergers & acquisitions", 
                         "m&a", "corporate law", "legal documentation", "policy compliance", 
                         "contract", "agreement", "terms", "policy", "regulation", "lawsuit", 
                         "copyright", "trademark", "patent", "non-disclosure", "nda", "privacy policy", 
                         "terms of service", "liability", "warranty", "indemnification", "arbitration", 
                         "clause", "amendment", "addendum", "legal notice", "cease and desist"]
        
        # Check HR keywords
        if any(keyword in content_lower for keyword in hr_keywords) or any(keyword in filename for keyword in ["hr", "employee", "personnel", "training", "benefits", "recruitment", "onboarding"]):
            doc_type = "hr_document"
            department = "hr"
            confidence = 0.95
            priority = "medium"
            tags = ["hr", "employee", "personnel"]
        # Check Finance keywords
        elif any(keyword in content_lower for keyword in finance_keywords) or any(keyword in filename for keyword in ["finance", "invoice", "bill", "payment", "budget", "accounting"]):
            doc_type = "financial_document"
            department = "finance"
            confidence = 0.95
            priority = "high"
            tags = ["finance", "invoice", "payment"]
        # Check Legal keywords  
        elif any(keyword in content_lower for keyword in legal_keywords) or any(keyword in filename for keyword in ["legal", "contract", "agreement", "compliance", "policy", "nda"])
              "contract" in filename or "agreement" in filename or "legal" in filename or "nda" in filename or
              "policy" in filename or "compliance" in filename):
            doc_type = "legal_document"
            department = "legal"
            confidence = 0.85
            priority = "high"
            tags = ["legal", "contract", "compliance"]
        elif ("employee" in content_lower or "hr" in content_lower or "human resources" in content_lower or
              "personnel" in content_lower or "hiring" in content_lower or "training" in content_lower or
              "performance" in content_lower or "recruitment" in content_lower or "onboarding" in content_lower or
              "benefits" in content_lower or "leave" in content_lower or "vacation" in content_lower or
              "disciplinary" in content_lower or "termination" in content_lower or "resignation" in content_lower or
              "promotion" in content_lower or "performance review" in content_lower or "appraisal" in content_lower or
              "job description" in content_lower or "workplace policy" in content_lower or "harassment" in content_lower or
              "hr" in filename or "employee" in filename or "personnel" in filename or "hiring" in filename or
              "training" in filename or "benefits" in filename or "leave" in filename or "performance" in filename):
            doc_type = "hr_document"
            department = "hr"
            confidence = 0.85
            priority = "medium"
            tags = ["hr", "employee", "personnel"]
        elif ("it" in content_lower or "technology" in content_lower or
              "it" in filename or "tech" in filename):
            doc_type = "it_document"
            department = "it"
            confidence = 0.75
            priority = "medium"
            tags = ["it", "technology"]
        else:
            doc_type = "general_document"
            department = "general"
            confidence = 0.6
            priority = "low"
            tags = ["general"]

        logger.info(f"Classified document {file.filename} as {doc_type}")

        return ClassificationResponse(
            doc_type=doc_type,
            department=department,
            confidence=confidence,
            priority=priority,
            extracted_text=text_content[:500],
            page_count=1,
            language="en",
            tags=tags
        )
            
    except Exception as e:
        logger.error(f"Classification error: {e}")
        return ClassificationResponse(
            doc_type="general_document",
            department="general", 
            confidence=0.3,
            priority="low",
            extracted_text="",
            page_count=1,
            language="en",
            tags=["general"]
        )

@app.get("/ping")
async def ping():
    return {"message": "pong from Classification Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)