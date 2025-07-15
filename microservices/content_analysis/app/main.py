from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os
import uvicorn
import re
import hashlib
from typing import Dict, List, Optional
from collections import Counter
import nltk
from textstat import flesch_reading_ease

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize

app = FastAPI(title="Content Analysis Service")

class AnalysisRequest(BaseModel):
    doc_id: str
    content: str
    filename: Optional[str] = None

class EntityExtractionResult(BaseModel):
    names: List[str]
    dates: List[str]
    emails: List[str]
    amounts: List[str]
    phone_numbers: List[str]
    addresses: List[str]

class AnalysisResponse(BaseModel):
    doc_id: str
    entities: EntityExtractionResult
    sentiment: str
    risk_score: float
    confidentiality_percent: float
    word_count: int
    char_count: int
    language: str
    readability_score: float
    summary: str
    key_phrases: List[str]
    analysis_status: str

def extract_entities(content: str) -> EntityExtractionResult:
    """Extract various entities from document content"""

    # Extract names (capitalized words, improved pattern)
    names = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b', content)
    names = list(set(names))  # Remove duplicates

    # Extract dates (multiple formats)
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',  # DD Month YYYY
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}'  # Month DD, YYYY
    ]
    dates = []
    for pattern in date_patterns:
        dates.extend(re.findall(pattern, content, re.IGNORECASE))
    dates = list(set(dates))

    # Extract emails
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
    emails = list(set(emails))

    # Extract amounts/currency (improved pattern)
    amount_patterns = [
        r'\$\d+(?:,\d{3})*(?:\.\d{2})?',  # $1,000.00
        r'\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|CAD)',  # 1000.00 USD
        r'(?:USD|EUR|GBP|CAD)\s*\d+(?:,\d{3})*(?:\.\d{2})?',  # USD 1000.00
    ]
    amounts = []
    for pattern in amount_patterns:
        amounts.extend(re.findall(pattern, content, re.IGNORECASE))
    amounts = list(set(amounts))

    # Extract phone numbers
    phone_patterns = [
        r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',  # US format
        r'\+?[0-9]{1,3}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,9}'  # International
    ]
    phone_numbers = []
    for pattern in phone_patterns:
        phone_numbers.extend(re.findall(pattern, content))
    phone_numbers = list(set(phone_numbers))

    # Extract addresses (basic pattern)
    address_pattern = r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl)\b'
    addresses = re.findall(address_pattern, content, re.IGNORECASE)
    addresses = list(set(addresses))

    return EntityExtractionResult(
        names=names[:10],  # Limit to top 10
        dates=dates[:10],
        emails=emails[:10],
        amounts=amounts[:10],
        phone_numbers=phone_numbers[:10],
        addresses=addresses[:10]
    )

def analyze_sentiment(content: str) -> str:
    """Simple sentiment analysis based on keywords"""
    positive_words = ['good', 'excellent', 'great', 'positive', 'success', 'approve', 'accept', 'agree', 'satisfied', 'happy']
    negative_words = ['bad', 'terrible', 'negative', 'fail', 'reject', 'deny', 'disagree', 'unsatisfied', 'angry', 'disappointed']

    content_lower = content.lower()
    positive_count = sum(1 for word in positive_words if word in content_lower)
    negative_count = sum(1 for word in negative_words if word in content_lower)

    if positive_count > negative_count:
        return "positive"
    elif negative_count > positive_count:
        return "negative"
    else:
        return "neutral"

def calculate_risk_score(content: str, entities: EntityExtractionResult) -> float:
    """Calculate document risk score based on content and entities"""
    risk_score = 0.0
    content_lower = content.lower()

    # Risk factors
    confidential_keywords = ['confidential', 'private', 'sensitive', 'classified', 'restricted', 'internal only']
    legal_keywords = ['contract', 'agreement', 'legal', 'lawsuit', 'litigation', 'compliance']
    financial_keywords = ['payment', 'invoice', 'bank', 'account', 'credit card', 'social security']

    # Check for confidential content
    if any(word in content_lower for word in confidential_keywords):
        risk_score += 0.3

    # Check for legal content
    if any(word in content_lower for word in legal_keywords):
        risk_score += 0.2

    # Check for financial content
    if any(word in content_lower for word in financial_keywords):
        risk_score += 0.2

    # Risk based on entities
    if entities.amounts:
        risk_score += 0.1
    if entities.emails:
        risk_score += 0.1
    if entities.phone_numbers:
        risk_score += 0.1

    return min(risk_score, 1.0)

def calculate_confidentiality_score(content: str, entities: EntityExtractionResult) -> float:
    """Calculate confidentiality percentage based on content analysis"""
    confidentiality_score = 0.0
    content_lower = content.lower()

    # High confidentiality indicators
    high_conf_keywords = ['confidential', 'classified', 'restricted', 'top secret', 'proprietary']
    medium_conf_keywords = ['internal', 'private', 'sensitive', 'do not distribute', 'limited access']
    personal_info = ['ssn', 'social security', 'credit card', 'bank account', 'password']

    # Check for high confidentiality keywords
    if any(word in content_lower for word in high_conf_keywords):
        confidentiality_score += 0.4

    # Check for medium confidentiality keywords
    if any(word in content_lower for word in medium_conf_keywords):
        confidentiality_score += 0.3

    # Check for personal information
    if any(word in content_lower for word in personal_info):
        confidentiality_score += 0.2

    # Based on entities found
    if entities.amounts:
        confidentiality_score += 0.1
    if entities.emails:
        confidentiality_score += 0.05
    if entities.phone_numbers:
        confidentiality_score += 0.05

    return min(confidentiality_score * 100, 100.0)  # Return as percentage

def calculate_readability_score(content: str) -> float:
    """Simple readability score calculation"""
    words = content.split()
    sentences = content.split('.')

    if len(sentences) == 0 or len(words) == 0:
        return 0.0

    avg_sentence_length = len(words) / len(sentences)
    avg_word_length = sum(len(word) for word in words) / len(words)

    # Simple readability formula (lower is better)
    score = (avg_sentence_length * 0.3) + (avg_word_length * 0.7)

    # Normalize to 0-1 scale (1 = most readable)
    normalized_score = max(0, min(1, 1 - (score / 20)))

    return round(normalized_score, 2)

def extract_key_phrases(content: str) -> List[str]:
    """Extract key phrases from content"""
    # Simple key phrase extraction based on frequency
    words = re.findall(r'\b[A-Za-z]{3,}\b', content.lower())
    word_freq = {}

    for word in words:
        if word not in ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use']:
            word_freq[word] = word_freq.get(word, 0) + 1

    # Get top words
    key_phrases = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    return [phrase[0] for phrase in key_phrases]

def generate_summary(content: str) -> str:
    """Generate a comprehensive bullet-point summary that covers the entire document"""
    if not content or len(content.strip()) == 0:
        return "• Document uploaded successfully\n• Content analysis completed\n• Ready for review"

    # Clean and prepare content
    content = content.strip()
    content_words = content.split()
    total_words = len(content_words)
    
    # Split content into logical sections for comprehensive coverage
    sentences = [s.strip() for s in content.split('.') if len(s.strip()) > 10]
    paragraphs = [p.strip() for p in content.split('\n') if len(p.strip()) > 20]
    
    summary_points = []
    
    # 1. Document Type and Purpose (from beginning)
    first_part = content[:min(500, len(content))]
    purpose_keywords = ['purpose', 'objective', 'goal', 'aim', 'intention', 'subject', 'regarding', 'about', 'concerning']
    
    for sentence in sentences[:5]:
        if len(sentence) > 20:
            if any(keyword in sentence.lower() for keyword in purpose_keywords):
                summary_points.append(f"• Document Purpose: {sentence}")
                break
    
    if not any('purpose' in point.lower() for point in summary_points):
        # Use first meaningful sentence
        for sentence in sentences[:3]:
            if len(sentence) > 25 and len(sentence.split()) >= 6:
                summary_points.append(f"• Document Overview: {sentence}")
                break
    
    # 2. Key Information from Beginning Section (First 25% of document)
    beginning_section = content[:len(content)//4]
    beginning_sentences = [s.strip() for s in beginning_section.split('.') if len(s.strip()) > 15]
    
    info_count = 0
    for sentence in beginning_sentences[:5]:
        if info_count >= 2:
            break
        # Skip if already covered in purpose
        if not any(len(set(sentence.lower().split()) & set(point.lower().split())) > len(sentence.split()) * 0.4 
                  for point in summary_points):
            summary_points.append(f"• Key Information: {sentence}")
            info_count += 1
    
    # 3. Action Items and Requirements
    action_keywords = ['must', 'required', 'need', 'should', 'request', 'action', 'submit', 'complete', 'deadline', 'due', 'urgent', 'immediate', 'approve', 'review']
    action_points = []
    
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in action_keywords) and len(sentence) > 15:
            action_points.append(sentence)
    
    if action_points:
        summary_points.append(f"• Required Actions: {action_points[0]}")
        if len(action_points) > 1:
            summary_points.append(f"• Additional Requirements: {action_points[1]}")
    
    # 4. Financial/Numerical Information
    financial_keywords = ['cost', 'price', 'amount', 'budget', 'payment', 'invoice', 'expense', 'revenue', 'salary', 'fee', 'charge']
    import re
    
    # Find sentences with numbers or financial terms
    financial_sentences = []
    for sentence in sentences:
        if (any(keyword in sentence.lower() for keyword in financial_keywords) or 
            re.search(r'\$\d+|\d+\.\d+|\d+%|\d+,\d+', sentence)) and len(sentence) > 15:
            financial_sentences.append(sentence)
    
    if financial_sentences:
        summary_points.append(f"• Financial Details: {financial_sentences[0]}")
    
    # 5. People, Departments, and Roles
    people_keywords = ['employee', 'manager', 'director', 'supervisor', 'team', 'department', 'hr', 'finance', 'legal', 'it', 'staff', 'personnel', 'admin']
    people_sentences = []
    
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in people_keywords) and len(sentence) > 15:
            people_sentences.append(sentence)
    
    if people_sentences:
        summary_points.append(f"• Personnel/Departments: {people_sentences[0]}")
    
    # 6. Dates and Timeline Information
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',  # DD Month YYYY
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}'  # Month DD, YYYY
    ]
    
    date_sentences = []
    timeline_keywords = ['deadline', 'due', 'schedule', 'date', 'time', 'when', 'by', 'until', 'before', 'after']
    
    for sentence in sentences:
        has_date = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in date_patterns)
        has_timeline = any(keyword in sentence.lower() for keyword in timeline_keywords)
        
        if (has_date or has_timeline) and len(sentence) > 15:
            date_sentences.append(sentence)
    
    if date_sentences:
        summary_points.append(f"• Timeline/Dates: {date_sentences[0]}")
    
    # 7. Middle Section Content (25%-75% of document)
    middle_start = len(content)//4
    middle_end = 3*len(content)//4
    middle_section = content[middle_start:middle_end]
    middle_sentences = [s.strip() for s in middle_section.split('.') if len(s.strip()) > 20]
    
    # Get most informative sentences from middle section
    middle_info = []
    for sentence in middle_sentences[:8]:
        # Score sentence based on information density
        score = 0
        words = sentence.split()
        
        # Length scoring
        if 10 <= len(words) <= 30:
            score += 3
        
        # Contains important keywords
        important_keywords = ['important', 'critical', 'key', 'main', 'primary', 'significant', 'essential', 'major']
        if any(keyword in sentence.lower() for keyword in important_keywords):
            score += 2
        
        # Contains specifics (numbers, names, etc.)
        if re.search(r'\d+|[A-Z][a-z]+\s+[A-Z][a-z]+', sentence):
            score += 1
        
        if score >= 2:
            # Check if not already covered
            already_covered = False
            for point in summary_points:
                common_words = set(sentence.lower().split()) & set(point.lower().split())
                if len(common_words) > len(sentence.split()) * 0.3:
                    already_covered = True
                    break
            
            if not already_covered:
                middle_info.append(sentence)
    
    # Add best middle section content
    for i, sentence in enumerate(middle_info[:2]):
        summary_points.append(f"• Core Content: {sentence}")
    
    # 8. Process/Procedure Information
    process_keywords = ['process', 'procedure', 'workflow', 'steps', 'method', 'approach', 'guidelines', 'instructions', 'protocol']
    process_sentences = []
    
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in process_keywords) and len(sentence) > 15:
            process_sentences.append(sentence)
    
    if process_sentences:
        summary_points.append(f"• Process/Procedures: {process_sentences[0]}")
    
    # 9. Final Section Content (Last 25% of document)
    final_section = content[3*len(content)//4:]
    final_sentences = [s.strip() for s in final_section.split('.') if len(s.strip()) > 15]
    
    conclusion_keywords = ['conclusion', 'summary', 'result', 'outcome', 'decision', 'recommendation', 'next steps', 'follow up', 'finally']
    conclusion_found = False
    
    for sentence in final_sentences:
        if any(keyword in sentence.lower() for keyword in conclusion_keywords) and len(sentence) > 15:
            summary_points.append(f"• Conclusion/Next Steps: {sentence}")
            conclusion_found = True
            break
    
    if not conclusion_found and final_sentences:
        # Add the most substantial final sentence
        for sentence in reversed(final_sentences[:3]):
            if len(sentence) > 20:
                summary_points.append(f"• Final Points: {sentence}")
                break
    
    # 10. Ensure comprehensive coverage - fill gaps if document has more content
    current_coverage = sum(len(point) for point in summary_points)
    if current_coverage < min(800, len(content) * 0.15):  # Ensure at least 15% coverage or 800 chars
        
        # Find uncovered important sentences
        all_covered_words = set()
        for point in summary_points:
            all_covered_words.update(point.lower().split())
        
        remaining_sentences = []
        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            overlap = len(sentence_words & all_covered_words)
            if overlap < len(sentence_words) * 0.4 and len(sentence) > 20:  # Less than 40% overlap
                remaining_sentences.append(sentence)
        
        # Add most informative remaining sentences
        for sentence in remaining_sentences[:3]:
            if len(summary_points) < 12:  # Max limit
                summary_points.append(f"• Additional Content: {sentence}")
    
    # Ensure we have minimum coverage for comprehensive summary
    if len(summary_points) < 4:
        # Add more content to ensure comprehensive coverage
        for sentence in sentences[:10]:
            if len(summary_points) >= 8:
                break
            if len(sentence) > 25:
                # Check if not already covered
                already_covered = False
                for point in summary_points:
                    if any(word in point.lower() for word in sentence.lower().split()[:4]):
                        already_covered = True
                        break
                
                if not already_covered:
                    summary_points.append(f"• Document Content: {sentence}")
    
    # Limit to maximum 10 points for readability
    if len(summary_points) > 10:
        summary_points = summary_points[:10]
    
    # Create final summary
    final_summary = '\n'.join(summary_points)
    
    # If still no comprehensive summary, create from chunks
    if not summary_points or len(final_summary) < 100:
        chunk_size = max(50, total_words // 6)  # Divide into 6 chunks
        chunks = []
        
        for i in range(0, len(content_words), chunk_size):
            chunk = ' '.join(content_words[i:i+chunk_size])
            if len(chunk) > 30:
                chunks.append(chunk)
        
        summary_points = []
        for i, chunk in enumerate(chunks[:8]):
            summary_points.append(f"• Section {i+1}: {chunk[:120]}{'...' if len(chunk) > 120 else ''}")
        
        final_summary = '\n'.join(summary_points)
    
    return final_summary if final_summary else "• Document processed and ready for comprehensive review"

def detect_language(content: str) -> str:
    """Simple language detection"""
    # This is a very basic implementation
    # In a real system, you'd use a proper language detection library
    common_english_words = ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how']

    content_lower = content.lower()
    english_word_count = sum(1 for word in common_english_words if word in content_lower)

    return "en" if english_word_count > 3 else "unknown"

@app.get("/")
async def root():
    return {"message": "Content Analysis Service is running", "service": "content_analysis"}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_content(request: AnalysisRequest):
    """Analyze document content for entities, sentiment, and metadata"""
    try:
        content = request.content

        if not content or len(content.strip()) == 0:
            raise HTTPException(status_code=400, detail="Content cannot be empty")

        # Extract entities
        entities = extract_entities(content)

        # Analyze sentiment
        sentiment = analyze_sentiment(content)

        # Calculate risk score
        risk_score = calculate_risk_score(content, entities)

        # Calculate confidentiality percentage
        confidentiality_percent = calculate_confidentiality_score(content, entities)

        # Calculate readability
        readability_score = calculate_readability_score(content)

        # Extract key phrases
        key_phrases = extract_key_phrases(content)

        # Generate summary
        summary = generate_summary(content)

        # Detect language
        language = detect_language(content)

        # Calculate metrics
        word_count = len(content.split())
        char_count = len(content)

        return AnalysisResponse(
            doc_id=request.doc_id,
            entities=entities,
            sentiment=sentiment,
            risk_score=risk_score,
            confidentiality_percent=confidentiality_percent,
            word_count=word_count,
            char_count=char_count,
            language=language,
            readability_score=readability_score,
            summary=summary,
            key_phrases=key_phrases,
            analysis_status="completed"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/ping")
async def ping():
    return {"message": "pong from Content Analysis Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)