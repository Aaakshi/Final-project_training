from fastapi import FastAPI
from pydantic import BaseModel
import sys
import os
import uvicorn
import re

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from libs.utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

app = FastAPI(title="Content Analysis Service")

class AnalysisRequest(BaseModel):
    doc_id: str
    content: str

class AnalysisResponse(BaseModel):
    entities: dict
    summary: str
    key_phrases: list
    sentiment: str
    readability_score: float
    risk_score: float
    confidentiality_percent: float
    metadata: dict

def extract_entities(content: str) -> dict:
    """Extract entities from content"""
    entities = {
        "names": [],
        "dates": [],
        "amounts": [],
        "organizations": [],
        "locations": []
    }

    # Extract dates
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',
        r'\d{2}/\d{2}/\d{4}',
        r'\d{2}-\d{2}-\d{4}',
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
    ]
    for pattern in date_patterns:
        entities["dates"].extend(re.findall(pattern, content, re.IGNORECASE))

    # Extract potential names (capitalized words)
    name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
    entities["names"] = re.findall(name_pattern, content)

    # Extract amounts
    amount_patterns = [
        r'\$\d+\.?\d*',
        r'\d+\.\d+\s*(?:dollars?|USD)',
        r'\b\d+,\d+(?:\.\d+)?\b'
    ]
    for pattern in amount_patterns:
        entities["amounts"].extend(re.findall(pattern, content))

    return entities

def extract_key_phrases(content: str) -> list:
    """Extract key phrases from content"""
    key_phrases = []

    # Important business terms
    business_keywords = [
        'contract', 'agreement', 'policy', 'procedure', 'deadline', 'budget',
        'invoice', 'payment', 'employee', 'department', 'manager', 'director',
        'project', 'meeting', 'review', 'approval', 'compliance', 'audit',
        'training', 'benefits', 'salary', 'performance', 'evaluation'
    ]

    content_lower = content.lower()
    for keyword in business_keywords:
        if keyword in content_lower:
            key_phrases.append(keyword.title())

    return list(set(key_phrases))[:10]  # Limit to 10 unique phrases

def calculate_readability_score(content: str) -> float:
    """Calculate basic readability score"""
    words = content.split()
    sentences = re.split(r'[.!?]+', content)

    if len(sentences) == 0 or len(words) == 0:
        return 0.5

    avg_words_per_sentence = len(words) / max(len(sentences), 1)

    # Simple readability: lower score for longer sentences
    if avg_words_per_sentence < 15:
        return 0.8
    elif avg_words_per_sentence < 25:
        return 0.6
    else:
        return 0.4

def calculate_risk_score(content: str, entities: dict) -> float:
    """Calculate risk score based on content"""
    risk_score = 0.0
    content_lower = content.lower()

    # High risk keywords
    high_risk_keywords = ['urgent', 'immediate', 'deadline', 'legal', 'lawsuit', 'compliance', 'violation', 'emergency']
    medium_risk_keywords = ['review', 'approve', 'action required', 'important', 'attention']

    for keyword in high_risk_keywords:
        if keyword in content_lower:
            risk_score += 0.3

    for keyword in medium_risk_keywords:
        if keyword in content_lower:
            risk_score += 0.1

    return min(risk_score, 1.0)

def calculate_confidentiality_score(content: str) -> float:
    """Calculate confidentiality percentage based on document content"""
    content_lower = content.lower()
    
    # Very High confidentiality keywords (40-60 points each)
    very_high_conf_keywords = [
        'top secret', 'classified', 'confidential', 'restricted access', 'eyes only',
        'proprietary', 'trade secret', 'intellectual property', 'patent pending',
        'salary', 'wages', 'compensation', 'payroll', 'bonus', 'stock options',
        'ssn', 'social security number', 'tax id', 'ein', 'passport number',
        'medical records', 'health information', 'diagnosis', 'patient', 'hipaa',
        'criminal background', 'background check', 'drug test', 'investigation',
        'lawsuit', 'litigation', 'settlement', 'legal action', 'court case',
        'merger', 'acquisition', 'buyout', 'takeover', 'strategic acquisition',
        'board meeting', 'executive decision', 'ceo confidential', 'board resolution',
        'financial statements', 'audit report', 'tax return', 'insider information',
        'security clearance', 'access control', 'authentication', 'authorization'
    ]
    
    # High confidentiality keywords (25-40 points each)
    high_conf_keywords = [
        'private', 'internal only', 'confidentiality', 'non-disclosure', 'nda',
        'sensitive', 'privileged', 'restricted', 'proprietary information',
        'employee id', 'personnel file', 'hr record', 'employment history',
        'performance review', 'performance evaluation', 'appraisal', 'rating',
        'disciplinary action', 'warning', 'termination', 'firing', 'layoff',
        'contract negotiation', 'vendor agreement', 'supplier contract',
        'budget allocation', 'financial planning', 'cost analysis', 'profit margin',
        'customer list', 'client database', 'contact information', 'email list',
        'pricing strategy', 'cost structure', 'revenue model', 'business model',
        'strategic plan', 'business strategy', 'competitive analysis', 'swot analysis',
        'research and development', 'r&d', 'product development', 'innovation',
        'password', 'login credentials', 'access token', 'api key', 'security key',
        'bank account', 'routing number', 'account number', 'credit card',
        'personal information', 'pii', 'personally identifiable', 'data protection'
    ]
    
    # Medium confidentiality keywords (15-25 points each)
    medium_conf_keywords = [
        'employee', 'staff', 'personnel', 'workforce', 'team member',
        'hr', 'human resources', 'talent management', 'recruiting',
        'department', 'division', 'business unit', 'organizational',
        'manager', 'supervisor', 'director', 'vice president', 'executive',
        'project', 'initiative', 'program', 'campaign', 'operation',
        'budget', 'cost', 'expense', 'expenditure', 'financial',
        'revenue', 'income', 'profit', 'loss', 'earnings', 'sales',
        'contract', 'agreement', 'deal', 'partnership', 'collaboration',
        'vendor', 'supplier', 'contractor', 'third party', 'external',
        'client', 'customer', 'account', 'relationship', 'service',
        'meeting notes', 'discussion', 'conversation', 'consultation',
        'policy', 'procedure', 'guideline', 'protocol', 'standard',
        'training', 'development', 'education', 'certification', 'skill',
        'performance', 'productivity', 'efficiency', 'quality', 'metric',
        'deadline', 'timeline', 'schedule', 'milestone', 'deliverable',
        'risk', 'compliance', 'audit', 'regulation', 'governance'
    ]
    
    # Low confidentiality keywords (5-15 points each)
    low_conf_keywords = [
        'office', 'facility', 'building', 'location', 'address',
        'general', 'public', 'external', 'community', 'stakeholder',
        'calendar', 'schedule', 'appointment', 'meeting', 'event',
        'announcement', 'notification', 'update', 'news', 'information',
        'handbook', 'manual', 'guide', 'instruction', 'documentation',
        'process', 'workflow', 'procedure', 'step', 'task'
    ]
    
    # Public/Low sensitivity keywords (reduce score)
    public_keywords = [
        'public', 'open', 'transparent', 'published', 'announced',
        'press release', 'newsletter', 'blog post', 'social media',
        'marketing', 'advertisement', 'promotion', 'publicity',
        'general information', 'faq', 'help', 'support', 'tutorial'
    ]
    
    score = 0.0
    matched_keywords = []
    
    # Check for very high confidentiality content
    for keyword in very_high_conf_keywords:
        if keyword in content_lower:
            score += 50
            matched_keywords.append(keyword)
    
    # Check for high confidentiality content
    for keyword in high_conf_keywords:
        if keyword in content_lower:
            score += 32
            matched_keywords.append(keyword)
    
    # Check for medium confidentiality content
    for keyword in medium_conf_keywords:
        if keyword in content_lower:
            score += 20
            matched_keywords.append(keyword)
    
    # Check for low confidentiality content
    for keyword in low_conf_keywords:
        if keyword in content_lower:
            score += 10
            matched_keywords.append(keyword)
    
    # Check for public content (reduces score)
    for keyword in public_keywords:
        if keyword in content_lower:
            score -= 8
    
    # Enhanced pattern matching for sensitive data
    patterns = {
        r'\b\d{3}-\d{2}-\d{4}\b': 60,  # SSN pattern
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b': 55,  # Credit card pattern
        r'\$\d+(?:,\d{3})*(?:\.\d{2})?': 25,  # Money amounts
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b': 20,  # Email addresses
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b': 15,  # Phone numbers
        r'\bEMP\d+\b|\bID[-\s]?\d+\b': 30,  # Employee IDs
        r'\b\d{2}-\d{7}\b': 35,  # Account numbers
        r'\b[A-Z]{2}\d{6,8}\b': 40,  # License/ID patterns
        r'\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b': 55,  # Credit card with spaces
        r'\b[0-9]{9}\b': 25,  # 9-digit numbers (could be SSN without dashes)
    }
    
    for pattern, points in patterns.items():
        matches = re.findall(pattern, content)
        if matches:
            score += points * min(len(matches), 3)  # Cap at 3 matches per pattern
    
    # Document type and context indicators
    doc_type_indicators = {
        'salary review': 45,
        'compensation analysis': 45,
        'performance evaluation': 40,
        'disciplinary action': 50,
        'termination notice': 55,
        'background check': 50,
        'medical leave': 35,
        'family leave': 30,
        'personal time off': 25,
        'employee complaint': 40,
        'harassment report': 55,
        'security incident': 50,
        'data breach': 60,
        'financial audit': 45,
        'tax document': 50,
        'legal counsel': 45,
        'board minutes': 50,
        'executive summary': 35,
        'strategic planning': 40,
        'merger discussion': 55,
        'acquisition plan': 55,
        'layoff plan': 60,
        'restructuring': 45
    }
    
    for indicator, points in doc_type_indicators.items():
        if indicator in content_lower:
            score += points
    
    # Request/action type analysis
    if any(indicator in content_lower for indicator in ['request for', 'application for', 'asking for']):
        if any(sensitive in content_lower for sensitive in ['salary', 'raise', 'promotion', 'transfer', 'leave']):
            score += 25
        else:
            score += 15
    
    # Urgency and priority context
    if any(indicator in content_lower for indicator in ['urgent', 'immediate', 'asap', 'critical', 'emergency']):
        score += 15
    
    # Department-specific sensitivity
    if 'hr' in content_lower or 'human resources' in content_lower:
        score += 20
    if 'legal' in content_lower:
        score += 25
    if 'finance' in content_lower or 'accounting' in content_lower:
        score += 22
    if 'executive' in content_lower or 'board' in content_lower:
        score += 30
    
    # Document length consideration (longer docs might contain more sensitive info)
    word_count = len(content.split())
    if word_count > 500:
        score += 5
    elif word_count > 1000:
        score += 10
    
    # Normalize score to percentage (0-100)
    normalized_score = min(100, max(0, score))
    
    return normalized_score

def generate_summary(content: str) -> str:
    """Generate intelligent bullet-point summary that analyzes and summarizes document content"""
    if not content or len(content.strip()) == 0:
        return "• Empty document uploaded\n• No content available for analysis\n• Please upload a document with text content"

    # Clean content
    content = content.strip().replace('\r\n', '\n').replace('\r', '\n')
    content_lower = content.lower()
    
    # Extract key information first
    summary_points = []
    
    # 1. Document Type and Purpose Analysis
    doc_purpose = ""
    if any(keyword in content_lower for keyword in ['request', 'application', 'asking', 'inquiry']):
        doc_purpose = "Employee request/inquiry document"
    elif any(keyword in content_lower for keyword in ['policy', 'procedure', 'guideline', 'rule']):
        doc_purpose = "Policy or procedural document"
    elif any(keyword in content_lower for keyword in ['invoice', 'bill', 'payment', 'receipt']):
        doc_purpose = "Financial/billing document"
    elif any(keyword in content_lower for keyword in ['contract', 'agreement', 'terms']):
        doc_purpose = "Legal/contractual document"
    elif any(keyword in content_lower for keyword in ['report', 'analysis', 'summary', 'findings']):
        doc_purpose = "Report or analysis document"
    else:
        doc_purpose = "General business document"
    
    summary_points.append(f"• Document Type: {doc_purpose}")
    
    # 2. Key People and Departments
    people_mentioned = []
    dept_pattern = r'\b(?:hr|human resources|finance|legal|it|marketing|sales|operations|administration)\b'
    departments = list(set(re.findall(dept_pattern, content_lower)))
    
    name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
    names = re.findall(name_pattern, content)
    
    if names:
        people_mentioned = list(set(names))[:3]  # Limit to 3 names
    
    people_info = []
    if people_mentioned:
        people_info.append(f"People: {', '.join(people_mentioned)}")
    if departments:
        people_info.append(f"Departments: {', '.join(departments).upper()}")
    
    if people_info:
        summary_points.append(f"• Key Stakeholders: {' | '.join(people_info)}")
    
    # 3. Main Requests or Actions - Enhanced for better extraction
    action_items = []
    
    # Look for specific request patterns with better context
    if 'remote work' in content_lower or 'work from home' in content_lower:
        action_items.append("Request for remote work flexibility")
    
    if 'leave balance' in content_lower or 'annual leave' in content_lower or 'vacation' in content_lower:
        action_items.append("Request for leave balance inquiry")
    
    if 'training' in content_lower and ('nomina' in content_lower or 'enroll' in content_lower):
        action_items.append("Request for training enrollment")
    
    if 'insurance' in content_lower and ('coverage' in content_lower or 'enrollment' in content_lower):
        action_items.append("Request for insurance information")
    
    # Generic pattern matching as fallback
    request_patterns = [
        (r'request(?:ing)?\s+(?:for\s+)?(.{10,40}?)(?:\.|,|\n|and)', 'Request for'),
        (r'would like\s+(?:to\s+)?(.{10,40}?)(?:\.|,|\n)', 'Would like to'),
        (r'asking\s+(?:for\s+)?(.{10,40}?)(?:\.|,|\n)', 'Asking for'),
    ]
    
    for pattern, prefix in request_patterns:
        matches = re.findall(pattern, content_lower, re.IGNORECASE)
        for match in matches[:2]:
            clean_match = match.strip()
            if len(clean_match) > 8 and clean_match not in str(action_items):
                action_items.append(f"{prefix} {clean_match}")
    
    if action_items:
        for i, item in enumerate(action_items[:3], 1):
            summary_points.append(f"• Request {i}: {item}")
    
    # 4. Important Dates and Deadlines
    date_info = []
    timeline_info = []
    
    # Find specific dates
    date_patterns = [
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b',
        r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b'
    ]
    
    for pattern in date_patterns:
        dates = re.findall(pattern, content)
        date_info.extend(dates[:3])
    
    # Look for timeline context
    if 'august' in content_lower and '2025' in content_lower:
        timeline_info.append("Starting August 2025")
    if 'september' in content_lower:
        timeline_info.append("September planning mentioned")
    
    if date_info or timeline_info:
        date_summary = []
        if date_info:
            date_summary.append(f"Dates: {', '.join(set(date_info[:3]))}")
        if timeline_info:
            date_summary.append(f"Timeline: {' | '.join(timeline_info[:2])}")
        summary_points.append(f"• Important Dates: {' | '.join(date_summary)}")
    
    # 5. Key Topics and Categories
    topic_keywords = {
        'Remote Work': ['remote work', 'work from home', 'flexible work', 'home office'],
        'Leave Management': ['leave balance', 'annual leave', 'vacation', 'time off', 'pto'],
        'Training': ['training', 'course', 'workshop', 'development', 'skill building'],
        'Benefits': ['insurance', 'benefits', 'health coverage', 'medical plan'],
        'HR Policies': ['policy', 'procedure', 'hr', 'human resources'],
        'Performance': ['performance', 'review', 'evaluation', 'assessment']
    }
    
    identified_topics = []
    for topic, keywords in topic_keywords.items():
        if any(keyword in content_lower for keyword in keywords):
            identified_topics.append(topic)
    
    if identified_topics:
        summary_points.append(f"• Main Topics: {', '.join(identified_topics[:4])}")
    
    # 6. Urgency and Priority Indicators
    urgency_keywords = ['urgent', 'immediate', 'asap', 'priority', 'critical', 'important']
    urgent_indicators = [keyword for keyword in urgency_keywords if keyword in content_lower]
    
    if urgent_indicators:
        summary_points.append(f"• Priority Level: High - contains {', '.join(urgent_indicators[:3])}")
    else:
        summary_points.append(f"• Priority Level: Standard request")
    
    # 7. Document Conclusion/Next Steps
    next_steps = []
    if 'please let me know' in content_lower:
        next_steps.append("Awaiting response from HR")
    if 'documentation' in content_lower or 'application' in content_lower:
        next_steps.append("May require additional documentation")
    if 'thank you' in content_lower:
        next_steps.append("Formal request submitted")
    
    if next_steps:
        summary_points.append(f"• Next Steps: {' | '.join(next_steps[:2])}")
    
    # Ensure we have meaningful content
    if len(summary_points) < 4:
        # Add content overview from first sentences
        sentences = [s.strip() for s in re.split(r'[.!?]+', content) if len(s.strip()) > 20]
        if sentences:
            summary_points.append(f"• Content Overview: {sentences[0][:80]}...")
    
    return '\n'.join(summary_points[:8])

@app.get("/")
async def root():
    return {"message": "Content Analysis Service is running", "service": "content_analysis"}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_content(request: AnalysisRequest):
    """Analyze document content and return comprehensive analysis"""
    try:
        # Extract entities
        entities = extract_entities(request.content)

        # Generate intelligent summary
        summary = generate_summary(request.content)

        # Extract key phrases
        key_phrases = extract_key_phrases(request.content)

        # Calculate readability score
        readability_score = calculate_readability_score(request.content)

        # Calculate risk score
        risk_score = calculate_risk_score(request.content, entities)

        # Calculate confidentiality score
        confidentiality_percent = calculate_confidentiality_score(request.content)

        # Basic sentiment analysis (simplified)
        sentiment = "neutral"
        positive_words = ["good", "excellent", "positive", "success", "approve", "great", "thank you", "appreciate"]
        negative_words = ["bad", "terrible", "negative", "fail", "reject", "poor", "urgent", "problem", "issue"]

        content_lower = request.content.lower()
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)

        if positive_count > negative_count:
            sentiment = "positive"
        elif negative_count > positive_count:
            sentiment = "negative"

        # Additional metadata
        metadata = {
            "word_count": len(request.content.split()),
            "sentence_count": len(re.split(r'[.!?]+', request.content)),
            "paragraph_count": len([p for p in request.content.split('\n\n') if p.strip()]),
            "avg_sentence_length": len(request.content.split()) / max(len(re.split(r'[.!?]+', request.content)), 1),
            "confidentiality_level": "High" if confidentiality_percent >= 70 else "Medium" if confidentiality_percent >= 30 else "Low"
        }

        logger.info(f"Analyzed content for document {request.doc_id} - Confidentiality: {confidentiality_percent:.1f}%")

        return AnalysisResponse(
            entities=entities,
            summary=summary,
            key_phrases=key_phrases,
            sentiment=sentiment,
            readability_score=readability_score,
            risk_score=risk_score,
            confidentiality_percent=confidentiality_percent,
            metadata=metadata
        )

    except Exception as e:
        logger.error(f"Content analysis error: {e}")
        return AnalysisResponse(
            entities={"names": [], "dates": [], "amounts": [], "organizations": [], "locations": []},
            summary="• Document processing error occurred\n• Please try uploading again\n• Contact support if issue persists",
            key_phrases=[],
            sentiment="neutral",
            readability_score=0.5,
            risk_score=0.1,
            confidentiality_percent=0.0,
            metadata={"word_count": 0, "sentence_count": 0, "paragraph_count": 0, "avg_sentence_length": 0, "confidentiality_level": "Low"}
        )

@app.get("/ping")
async def ping():
    return {"message": "pong from Content Analysis Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)