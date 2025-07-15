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
    
    # Split content into sentences and clean them
    sentences = []
    for sent in content.replace('\n', '. ').split('.'):
        sent = sent.strip()
        if len(sent) > 15 and len(sent.split()) >= 4:  # Meaningful sentences only
            sentences.append(sent)
    
    # If no good sentences, split by other punctuation
    if len(sentences) < 3:
        for sent in content.replace('\n', '! ').split('!'):
            sent = sent.strip()
            if len(sent) > 15 and len(sent.split()) >= 4:
                sentences.append(sent)
        for sent in content.replace('\n', '? ').split('?'):
            sent = sent.strip()
            if len(sent) > 15 and len(sent.split()) >= 4:
                sentences.append(sent)
    
    # If still no sentences, create from chunks
    if len(sentences) < 2:
        words = content.split()
        chunk_size = max(15, len(words) // 6)
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            if len(chunk) > 20:
                sentences.append(chunk)
    
    summary_points = []
    used_content = set()  # Track used content to avoid duplication
    
    # 1. Document Overview/Purpose (from first 25%)
    first_quarter = content[:len(content)//4]
    first_sentences = [s for s in sentences if s in first_quarter][:5]
    
    purpose_keywords = ['purpose', 'objective', 'goal', 'aim', 'subject', 'regarding', 'about', 'concerning', 'overview', 'introduction']
    purpose_found = False
    
    for sentence in first_sentences:
        if any(keyword in sentence.lower() for keyword in purpose_keywords):
            clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
            summary_points.append(f"• Document Purpose: {clean_sentence}")
            used_content.add(sentence.lower())
            purpose_found = True
            break
    
    if not purpose_found and first_sentences:
        clean_sentence = first_sentences[0][:100] + ("..." if len(first_sentences[0]) > 100 else "")
        summary_points.append(f"• Document Overview: {clean_sentence}")
        used_content.add(first_sentences[0].lower())
    
    # 2. Key Content from Beginning (remaining first 25%)
    remaining_first = [s for s in first_sentences if s.lower() not in used_content][:2]
    for sentence in remaining_first:
        clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
        summary_points.append(f"• Key Information: {clean_sentence}")
        used_content.add(sentence.lower())
    
    # 3. Action Items and Requirements
    action_keywords = ['must', 'required', 'need', 'should', 'request', 'action', 'submit', 'complete', 'deadline', 'due', 'urgent', 'immediate', 'approve', 'review', 'apply', 'process']
    action_sentences = []
    
    for sentence in sentences:
        if sentence.lower() not in used_content:
            if any(keyword in sentence.lower() for keyword in action_keywords):
                action_sentences.append(sentence)
    
    for sentence in action_sentences[:2]:
        clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
        summary_points.append(f"• Required Actions: {clean_sentence}")
        used_content.add(sentence.lower())
    
    # 4. Financial/Numerical Information
    financial_keywords = ['cost', 'price', 'amount', 'budget', 'payment', 'invoice', 'expense', 'revenue', 'salary', 'fee', 'charge', 'dollar', 'money', 'fund']
    import re
    
    financial_sentences = []
    for sentence in sentences:
        if sentence.lower() not in used_content:
            has_financial = any(keyword in sentence.lower() for keyword in financial_keywords)
            has_numbers = re.search(r'\$\d+|\d+\.\d+|\d+%|\d+,\d+|\d+ dollar', sentence)
            if has_financial or has_numbers:
                financial_sentences.append(sentence)
    
    for sentence in financial_sentences[:1]:
        clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
        summary_points.append(f"• Financial Details: {clean_sentence}")
        used_content.add(sentence.lower())
    
    # 5. Personnel and Departments
    people_keywords = ['employee', 'manager', 'director', 'supervisor', 'team', 'department', 'hr', 'finance', 'legal', 'it', 'staff', 'personnel', 'admin', 'worker', 'officer']
    people_sentences = []
    
    for sentence in sentences:
        if sentence.lower() not in used_content:
            if any(keyword in sentence.lower() for keyword in people_keywords):
                people_sentences.append(sentence)
    
    for sentence in people_sentences[:1]:
        clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
        summary_points.append(f"• Personnel/Departments: {clean_sentence}")
        used_content.add(sentence.lower())
    
    # 6. Dates and Timeline
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}'
    ]
    
    timeline_keywords = ['deadline', 'due', 'schedule', 'date', 'time', 'when', 'by', 'until', 'before', 'after', 'start', 'end', 'begin']
    date_sentences = []
    
    for sentence in sentences:
        if sentence.lower() not in used_content:
            has_date = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in date_patterns)
            has_timeline = any(keyword in sentence.lower() for keyword in timeline_keywords)
            if has_date or has_timeline:
                date_sentences.append(sentence)
    
    for sentence in date_sentences[:1]:
        clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
        summary_points.append(f"• Timeline/Dates: {clean_sentence}")
        used_content.add(sentence.lower())
    
    # 7. Core Content from Middle Section (25%-75%)
    middle_start = len(content) // 4
    middle_end = 3 * len(content) // 4
    middle_section = content[middle_start:middle_end]
    middle_sentences = [s for s in sentences if s in middle_section and s.lower() not in used_content]
    
    # Score and select best middle content
    scored_sentences = []
    for sentence in middle_sentences:
        score = 0
        words = sentence.split()
        
        # Length scoring
        if 8 <= len(words) <= 25:
            score += 3
        
        # Important keywords
        important_keywords = ['important', 'critical', 'key', 'main', 'primary', 'significant', 'essential', 'major', 'note', 'attention']
        if any(keyword in sentence.lower() for keyword in important_keywords):
            score += 2
        
        # Contains specifics
        if re.search(r'\d+|[A-Z][a-z]+\s+[A-Z][a-z]+', sentence):
            score += 1
        
        scored_sentences.append((score, sentence))
    
    # Sort by score and take top sentences
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    for score, sentence in scored_sentences[:2]:
        if score >= 2:
            clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
            summary_points.append(f"• Core Content: {clean_sentence}")
            used_content.add(sentence.lower())
    
    # 8. Process and Procedures
    process_keywords = ['process', 'procedure', 'workflow', 'steps', 'method', 'approach', 'guidelines', 'instructions', 'protocol', 'policy', 'rule']
    process_sentences = []
    
    for sentence in sentences:
        if sentence.lower() not in used_content:
            if any(keyword in sentence.lower() for keyword in process_keywords):
                process_sentences.append(sentence)
    
    for sentence in process_sentences[:1]:
        clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
        summary_points.append(f"• Process/Procedures: {clean_sentence}")
        used_content.add(sentence.lower())
    
    # 9. Final Section Content (Last 25%)
    final_section = content[3*len(content)//4:]
    final_sentences = [s for s in sentences if s in final_section and s.lower() not in used_content]
    
    conclusion_keywords = ['conclusion', 'summary', 'result', 'outcome', 'decision', 'recommendation', 'next steps', 'follow up', 'finally', 'therefore', 'thus']
    conclusion_found = False
    
    for sentence in final_sentences:
        if any(keyword in sentence.lower() for keyword in conclusion_keywords):
            clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
            summary_points.append(f"• Conclusion/Next Steps: {clean_sentence}")
            used_content.add(sentence.lower())
            conclusion_found = True
            break
    
    if not conclusion_found and final_sentences:
        sentence = final_sentences[-1]  # Last meaningful sentence
        clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
        summary_points.append(f"• Final Points: {clean_sentence}")
        used_content.add(sentence.lower())
    
    # 10. Fill gaps if needed to ensure comprehensive coverage
    if len(summary_points) < 6:
        remaining_sentences = [s for s in sentences if s.lower() not in used_content]
        # Score remaining sentences
        for sentence in remaining_sentences[:4]:
            if len(summary_points) >= 10:
                break
            clean_sentence = sentence[:100] + ("..." if len(sentence) > 100 else "")
            summary_points.append(f"• Additional Content: {clean_sentence}")
            used_content.add(sentence.lower())
    
    # Ensure we have at least 4 points
    if len(summary_points) < 4:
        # Create from document chunks
        chunk_size = max(30, total_words // 8)
        for i in range(0, min(len(content_words), chunk_size * 6), chunk_size):
            if len(summary_points) >= 8:
                break
            chunk = ' '.join(content_words[i:i+chunk_size])
            if len(chunk) > 30:
                clean_chunk = chunk[:100] + ("..." if len(chunk) > 100 else "")
                summary_points.append(f"• Section {len(summary_points)+1}: {clean_chunk}")
    
    # Limit to 10 points maximum for readability
    if len(summary_points) > 10:
        summary_points = summary_points[:10]
    
    # Create final summary with proper formatting
    final_summary = '\n'.join(summary_points)
    
    # Final fallback if somehow no summary was created
    if not summary_points or len(final_summary) < 50:
        final_summary = f"• Document Overview: Content analyzed and processed\n• Word Count: {total_words} words\n• Document Status: Ready for review\n• Content Type: {content[:100]}{'...' if len(content) > 100 else ''}"
    
    return final_summary

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