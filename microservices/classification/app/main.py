from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import sys
import os
import uvicorn
import json
import re
import hashlib
import PyPDF2
import docx
import tempfile
import uuid

app = FastAPI(title="Classification Service")

class ClassificationRequest(BaseModel):
    content: str
    filename: str
    file_type: str

class ClassificationResponse(BaseModel):
    doc_type: str
    department: str
    confidence: float
    priority: str
    extracted_text: str
    page_count: int
    language: str
    tags: list
    priority_keywords: list

def classify_document_locally(content: str, filename: str):
    """Enhanced local classification with comprehensive keywords"""
    # Handle large documents by limiting content length for processing
    content_to_analyze = content[:5000] if len(content) > 5000 else content
    content_lower = content_to_analyze.lower()
    filename_lower = filename.lower()

    # Enhanced priority classification keywords
    high_priority_keywords = [
        "by EOD", "by end of day", "by today", "asap", "urgent", "immediate", "within 24 hours", 
        "deadline today", "due today", "respond by", "reply immediately", "EOD", "end of day", "today",
        "action required", "requires immediate attention", "please review urgently", "high priority", 
        "critical issue", "resolve now", "immediate action", "urgent response",
        "escalated", "service disruption", "breach", "incident", "system down", "customer complaint", 
        "payment failed", "critical error", "emergency", "outage", "security breach",
        "today's meeting", "final review", "must attend", "confirmation needed", "urgent meeting"
    ]

    medium_priority_keywords = [
        "reminder", "follow up", "this week", "pending", "awaiting response", "check status", 
        "update needed", "follow-up", "status update",
        "by tomorrow", "due in 2 days", "schedule by", "before Friday", "complete by", "ETA",
        "due this week", "by end of week", "within 3 days",
        "scheduled for", "calendar invite", "tentative", "planned discussion", "agenda",
        "meeting request", "schedule meeting",
        "work in progress", "assigned", "need update", "submit by", "to be reviewed",
        "in progress", "task assigned", "please review"
    ]

    low_priority_keywords = [
        "for your information", "no action needed", "for record", "just sharing", 
        "reference document", "read only", "optional", "fyi", "for reference",
        "next quarter", "next month", "future release", "roadmap", "tentative plan", 
        "long-term goal", "backlog item", "future consideration",
        "weekly summary", "monthly report", "feedback", "draft version", "notes", 
        "not urgent", "informational", "general update"
    ]

    # Priority determination with weighted scoring
    priority_score = 0
    matched_keywords = []

    for keyword in high_priority_keywords:
        if keyword.lower() in content_lower or keyword.lower() in filename_lower:
            priority_score += 3
            matched_keywords.append(keyword)

    for keyword in medium_priority_keywords:
        if keyword.lower() in content_lower or keyword.lower() in filename_lower:
            priority_score += 2
            matched_keywords.append(keyword)

    for keyword in low_priority_keywords:
        if keyword.lower() in content_lower or keyword.lower() in filename_lower:
            priority_score += 1
            matched_keywords.append(keyword)

    # Determine final priority based on score
    if priority_score >= 6:
        keyword_priority = "high"
    elif priority_score >= 3:
        keyword_priority = "high" if any(kw.lower() in content_lower for kw in high_priority_keywords[:10]) else "medium"
    elif priority_score >= 2:
        keyword_priority = "medium"
    else:
        keyword_priority = "low"

    # Enhanced classification rules
    classification_rules = [
        {
            "keywords": ["hr", "human resources", "employee relations", "talent acquisition", "recruitment", 
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
                        "skill development", "career development"],
            "filename_keywords": ["hr", "human resources", "employee", "personnel", "hiring", "recruitment", 
                                 "training", "benefits", "leave", "performance", "onboarding", "handbook", 
                                 "policy", "staff", "workforce", "compensation", "evaluation", "talent", 
                                 "payroll", "engagement"],
            "doc_type": "hr_document",
            "department": "hr",
            "confidence": 0.95,
            "base_priority": "medium",
            "tags": ["hr", "employee", "personnel"]
        },
        {
            "keywords": ["finance", "financial planning", "budgeting", "accounting", "financial reporting", 
                        "accounts payable", "accounts receivable", "general ledger", "cash flow", 
                        "profit & loss", "balance sheet", "financial analysis", "treasury", 
                        "tax compliance", "auditing", "cost management", "revenue forecasting", 
                        "capital expenditure", "financial risk management", "erp", "enterprise resource planning", 
                        "invoice", "payment", "bill", "receipt", "expense", "revenue", "profit", "loss", 
                        "tax", "audit", "salary", "wage", "reimbursement", "cost", "expenditure", 
                        "vendor payment", "purchase order", "transaction", "bank statement", "credit", "debit", 
                        "financial", "fiscal", "budget", "expenditures"],
            "filename_keywords": ["finance", "financial", "budget", "accounting", "invoice", "bill", "receipt", 
                                 "payment", "expense", "tax", "audit", "payroll", "cost", "purchase", 
                                 "transaction", "bank", "credit", "debit", "treasury", "revenue", "profit", "loss"],
            "doc_type": "financial_document",
            "department": "finance",
            "confidence": 0.95,
            "base_priority": "high",
            "tags": ["finance", "accounting", "financial"]
        },
        {
            "keywords": ["legal", "compliance", "contracts", "corporate governance", "litigation", 
                        "regulatory affairs", "intellectual property", "ip", "risk management", 
                        "employment law", "data privacy", "gdpr", "general data protection regulation", 
                        "legal counsel", "dispute resolution", "due diligence", "mergers & acquisitions", 
                        "m&a", "corporate law", "legal documentation", "policy compliance", 
                        "contract", "agreement", "terms", "policy", "regulation", "lawsuit", 
                        "copyright", "trademark", "patent", "non-disclosure", "nda", "privacy policy", 
                        "terms of service", "liability", "warranty", "indemnification", "arbitration", 
                        "clause", "amendment", "addendum", "legal notice", "cease and desist", 
                        "attorney", "lawyer", "court", "judge", "settlement"],
            "filename_keywords": ["legal", "contract", "agreement", "terms", "compliance", "policy", "nda", 
                                 "lawsuit", "patent", "copyright", "trademark", "liability", "amendment", 
                                 "litigation", "gdpr", "governance", "regulatory", "intellectual property"],
            "doc_type": "legal_document",
            "department": "legal",
            "confidence": 0.95,
            "base_priority": "high",
            "tags": ["legal", "contract", "compliance"]
        },
        {
            "keywords": ["sales", "lead", "customer", "deal", "proposal", "quotation", "order", "client", 
                        "prospect", "opportunity", "pipeline", "crm", "revenue", "commission", "target", 
                        "forecast", "sales report", "customer acquisition", "retention", "upsell", 
                        "cross-sell", "conversion", "roi", "kpi", "territory", "account management"],
            "filename_keywords": ["sales", "lead", "proposal", "quote", "order", "client", "customer", 
                                 "deal", "opportunity", "pipeline", "forecast", "commission"],
            "doc_type": "sales_document",
            "department": "sales",
            "confidence": 0.90,
            "base_priority": "high",
            "tags": ["sales", "customer", "revenue"]
        },
        {
            "keywords": ["marketing", "campaign", "advertisement", "promotion", "brand", "social media", 
                        "digital marketing", "content marketing", "seo", "sem", "ppc", "email marketing", 
                        "influencer", "analytics", "metrics", "engagement", "reach", "impression", 
                        "conversion rate", "market research", "competitor analysis", "target audience", 
                        "demographic", "segmentation"],
            "filename_keywords": ["marketing", "campaign", "ad", "promo", "brand", "social", "seo", 
                                 "analytics", "content", "digital", "email"],
            "doc_type": "marketing_document",
            "department": "marketing",
            "confidence": 0.85,
            "base_priority": "medium",
            "tags": ["marketing", "campaign", "brand"]
        },
        {
            "keywords": ["technology", "it", "software", "hardware", "system", "network", "security", 
                        "server", "database", "infrastructure", "cybersecurity", "firewall", "backup", 
                        "cloud", "api", "integration", "deployment", "maintenance", "troubleshooting", 
                        "bug report", "feature request", "technical documentation", "user manual", 
                        "system requirements"],
            "filename_keywords": ["it", "tech", "software", "system", "network", "security", "server", 
                                 "database", "cloud", "api", "bug", "technical"],
            "doc_type": "it_document",
            "department": "it",
            "confidence": 0.88,
            "base_priority": "high",
            "tags": ["it", "technology", "technical"]
        },
        {
            "keywords": ["operations", "process", "workflow", "procedure", "logistics", "supply chain"],
            "filename_keywords": ["operations", "process", "workflow", "procedure"],
            "doc_type": "operations_document",
            "department": "operations",
            "confidence": 0.7,
            "base_priority": "medium",
            "tags": ["operations", "process"]
        },
        {
            "keywords": ["support", "ticket", "issue", "complaint", "feedback", "resolution"],
            "filename_keywords": ["support", "ticket", "issue"],
            "doc_type": "support_document",
            "department": "support",
            "confidence": 0.7,
            "base_priority": "medium",
            "tags": ["support", "customer"]
        },
        {
            "keywords": ["procurement", "purchase", "vendor", "supplier", "acquisition", "RFP"],
            "filename_keywords": ["procurement", "purchase", "vendor", "supplier"],
            "doc_type": "procurement_document",
            "department": "procurement",
            "confidence": 0.75,
            "base_priority": "medium",
            "tags": ["procurement", "purchase"]
        },
        {
            "keywords": ["product", "research", "development", "innovation", "design", "prototype"],
            "filename_keywords": ["product", "research", "development", "design"],
            "doc_type": "product_document",
            "department": "product",
            "confidence": 0.75,
            "base_priority": "medium",
            "tags": ["product", "research"]
        },
        {
            "keywords": ["administration", "admin", "office", "facility", "maintenance", "general"],
            "filename_keywords": ["admin", "office", "facility", "maintenance"],
            "doc_type": "admin_document",
            "department": "administration",
            "confidence": 0.6,
            "base_priority": "low",
            "tags": ["administration", "office"]
        },
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
            final_priority = keyword_priority
            if keyword_priority == "medium":
                final_priority = rule["base_priority"]

            return {
                "doc_type": rule["doc_type"],
                "department": rule["department"],
                "confidence": rule["confidence"],
                "priority": final_priority,
                "extracted_text": content[:1000],
                "page_count": 1,
                "language": "en",
                "tags": rule["tags"] + matched_keywords[:3],
                "priority_keywords": matched_keywords[:5]
            }

    # Default classification
    return {
        "doc_type": "general_document",
        "department": "general",
        "confidence": 0.5,
        "priority": keyword_priority,
        "extracted_text": content[:1000],
        "page_count": 1,
        "language": "en",
        "tags": ["general"] + matched_keywords[:3],
        "priority_keywords": matched_keywords[:5]
    }

@app.get("/")
async def root():
    return {"message": "Classification Service is running", "service": "classification"}

@app.post("/classify-text")
async def classify_text(request: ClassificationRequest):
    """Classify document based on text content"""
    try:
        content_lower = request.content.lower()
        filename_lower = request.filename.lower()

        # Enhanced classification logic with comprehensive keywords
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
                      "harassment", "diversity", "inclusion", "staff", "workforce", "compensation"]

        # Finance Keywords
        finance_keywords = ["finance", "financial", "accounting", "invoice", "receipt", "payment", 
                           "billing", "budget", "expense", "revenue", "profit", "loss", "tax", 
                           "audit", "financial statement", "balance sheet", "income statement", 
                           "cash flow", "accounts payable", "accounts receivable", "procurement", 
                           "purchase order", "vendor", "supplier", "cost", "pricing", "quote", 
                           "estimate", "contract value", "financial analysis", "roi", "investment"]

        # Legal Keywords  
        legal_keywords = ["legal", "law", "contract", "agreement", "terms", "conditions", "clause", 
                         "litigation", "compliance", "regulation", "policy", "procedure", "lawsuit", 
                         "settlement", "damages", "liability", "intellectual property", "copyright", 
                         "trademark", "patent", "confidentiality", "non-disclosure", "nda", 
                         "terms of service", "privacy policy", "legal notice", "attorney", "lawyer"]

        # IT Keywords
        it_keywords = ["it", "information technology", "software", "hardware", "system", "network", 
                      "security", "cybersecurity", "database", "server", "cloud", "infrastructure", 
                      "technical", "programming", "development", "application", "platform", 
                      "integration", "api", "maintenance", "support", "troubleshooting", "bug", 
                      "feature", "requirement", "specification", "architecture", "deployment"]

        # General Keywords
        general_keywords = ["general", "misc", "other", "administrative", "office", "facility", 
                           "maintenance", "general inquiry", "information", "announcement", 
                           "notification", "memo", "correspondence", "communication"]

        # Classification logic
        hr_score = sum(1 for keyword in hr_keywords if keyword in content_lower or keyword in filename_lower)
        finance_score = sum(1 for keyword in finance_keywords if keyword in content_lower or keyword in filename_lower)
        legal_score = sum(1 for keyword in legal_keywords if keyword in content_lower or keyword in filename_lower)
        it_score = sum(1 for keyword in it_keywords if keyword in content_lower or keyword in filename_lower)

        # Determine classification
        scores = {
            'hr_document': (hr_score, 'hr'),
            'invoice': (finance_score, 'finance'), 
            'contract': (legal_score, 'legal'),
            'it_document': (it_score, 'it'),
            'general': (0, 'administration')
        }

        # Find highest scoring category
        best_match = max(scores.items(), key=lambda x: x[1][0])
        doc_type, (score, department) = best_match

        # Determine priority based on keywords
        high_priority_keywords = ["urgent", "immediate", "asap", "critical", "emergency", "high priority"]
        medium_priority_keywords = ["important", "priority", "attention", "review"]

        priority = "low"
        if any(keyword in content_lower for keyword in high_priority_keywords):
            priority = "high"
        elif any(keyword in content_lower for keyword in medium_priority_keywords):
            priority = "medium"

        # If no clear classification, default to general
        if score == 0:
            doc_type = "general"
            department = "administration"

        return {
            "doc_type": doc_type,
            "department": department,
            "confidence": min(score / 5.0, 1.0),  # Normalize confidence score
            "priority": priority,
            "extracted_text": request.content[:1000],
            "page_count": 1,
            "language": "en",
            "tags": [doc_type, department, priority],
            "priority_keywords": high_priority_keywords if priority == "high" else medium_priority_keywords if priority == "medium" else []
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@app.post("/classify")
async def classify_document(file: UploadFile = File(...)):
    """Classify uploaded document file"""
    try:
        # Read file content
        content = await file.read()

        # Extract text based on file type
        text_content = ""
        if file.content_type == 'application/pdf':
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(content)
                    tmp_file.flush()

                    with open(tmp_file.name, 'rb') as pdf_file:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        text_parts = []
                        for page in pdf_reader.pages[:5]:
                            text_parts.append(page.extract_text())
                        text_content = '\n'.join(text_parts)
                os.unlink(tmp_file.name)
            except Exception as e:
                text_content = f"PDF document: {file.filename}"

        elif file.content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
                    tmp_file.write(content)
                    tmp_file.flush()

                    doc = docx.Document(tmp_file.name)
                    paragraphs = []
                    for para in doc.paragraphs[:50]:
                        if para.text.strip():
                            paragraphs.append(para.text.strip())
                    text_content = '\n'.join(paragraphs)
                os.unlink(tmp_file.name)
            except Exception as e:
                text_content = f"DOCX document: {file.filename}"

        elif file.content_type.startswith('text/'):
            text_content = content.decode('utf-8', errors='ignore')
        else:
            text_content = content.decode('utf-8', errors='ignore')[:5000]

        # Create classification request
        request = ClassificationRequest(
            content=text_content,
            filename=file.filename or "unknown",
            file_type=file.content_type or "txt"
        )

        # Use the text classification function
        classification_result = await classify_text(request)

        return classification_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File classification failed: {str(e)}")

@app.get("/ping")
async def ping():
    return {"message": "pong from Classification Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)