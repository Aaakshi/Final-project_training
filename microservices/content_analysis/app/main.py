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
    content = content.strip().replace('\r\n', '\n').replace('\r', '\n')
    content_words = content.split()
    total_words = len(content_words)
    
    # Split content into meaningful sentences
    sentences = []
    
    # First try splitting by periods, exclamation marks, and question marks
    import re
    sentence_endings = re.split(r'[.!?]+', content)
    
    for sent in sentence_endings:
        sent = sent.strip()
        # Filter out very short or meaningless sentences
        if len(sent) > 20 and len(sent.split()) >= 5:
            sentences.append(sent)
    
    # If we don't have enough sentences, try splitting by line breaks
    if len(sentences) < 3:
        line_sentences = content.split('\n')
        for sent in line_sentences:
            sent = sent.strip()
            if len(sent) > 20 and len(sent.split()) >= 5:
                sentences.append(sent)
    
    # Last resort: create chunks from the content
    if len(sentences) < 3:
        words = content.split()
        chunk_size = max(20, len(words) // 8)
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            if len(chunk) > 30:
                sentences.append(chunk)
    
    summary_points = []
    used_sentences = set()  # Track used sentences to avoid duplication
    
    # Strategy: Create comprehensive summary by analyzing different aspects
    
    # 1. Document Overview from beginning
    if len(sentences) > 0:
        first_sentence = sentences[0][:120] + ("..." if len(sentences[0]) > 120 else "")
        summary_points.append(f"• Document Overview: {first_sentence}")
        used_sentences.add(sentences[0])
    
    # 2. Extract key information by categories
    import re
    
    # Action items and requirements
    action_keywords = ['must', 'required', 'need', 'should', 'request', 'action', 'submit', 'complete', 'deadline', 'due', 'urgent', 'immediate', 'approve', 'review', 'apply', 'process']
    action_count = 0
    
    for sentence in sentences:
        if sentence not in used_sentences and action_count < 2:
            if any(keyword in sentence.lower() for keyword in action_keywords):
                clean_sentence = sentence[:120] + ("..." if len(sentence) > 120 else "")
                summary_points.append(f"• Action Required: {clean_sentence}")
                used_sentences.add(sentence)
                action_count += 1
    
    # Financial and numerical information
    financial_keywords = ['cost', 'price', 'amount', 'budget', 'payment', 'invoice', 'expense', 'revenue', 'salary', 'fee', 'charge', 'dollar', 'money', 'fund']
    financial_count = 0
    
    for sentence in sentences:
        if sentence not in used_sentences and financial_count < 1:
            has_financial = any(keyword in sentence.lower() for keyword in financial_keywords)
            has_numbers = re.search(r'\$\d+|\d+\.\d+|\d+%|\d+,\d+|\d+ dollars?', sentence)
            if has_financial or has_numbers:
                clean_sentence = sentence[:120] + ("..." if len(sentence) > 120 else "")
                summary_points.append(f"• Financial Details: {clean_sentence}")
                used_sentences.add(sentence)
                financial_count += 1
    
    # Personnel and department information
    people_keywords = ['employee', 'manager', 'director', 'supervisor', 'team', 'department', 'hr', 'finance', 'legal', 'it', 'staff', 'personnel', 'admin']
    people_count = 0
    
    for sentence in sentences:
        if sentence not in used_sentences and people_count < 1:
            if any(keyword in sentence.lower() for keyword in people_keywords):
                clean_sentence = sentence[:120] + ("..." if len(sentence) > 120 else "")
                summary_points.append(f"• Personnel/Department: {clean_sentence}")
                used_sentences.add(sentence)
                people_count += 1
    
    # Timeline and dates
    date_patterns = [r'\d{4}-\d{2}-\d{2}', r'\d{2}/\d{2}/\d{4}', r'\d{2}-\d{2}-\d{4}']
    timeline_keywords = ['deadline', 'due', 'schedule', 'date', 'time', 'when', 'by', 'until', 'before', 'after', 'start', 'end']
    timeline_count = 0
    
    for sentence in sentences:
        if sentence not in used_sentences and timeline_count < 1:
            has_date = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in date_patterns)
            has_timeline = any(keyword in sentence.lower() for keyword in timeline_keywords)
            if has_date or has_timeline:
                clean_sentence = sentence[:120] + ("..." if len(sentence) > 120 else "")
                summary_points.append(f"• Timeline/Dates: {clean_sentence}")
                used_sentences.add(sentence)
                timeline_count += 1
    
    # Fill with remaining important content to reach 6-8 bullet points
    remaining_sentences = [s for s in sentences if s not in used_sentences]
    
    # Score remaining sentences by importance
    scored_remaining = []
    for sentence in remaining_sentences:
        score = 0
        words = sentence.split()
        
        # Prefer medium-length sentences
        if 10 <= len(words) <= 30:
            score += 2
        
        # Important keywords
        important_keywords = ['important', 'critical', 'key', 'main', 'primary', 'significant', 'essential', 'note', 'attention', 'policy', 'procedure']
        if any(keyword in sentence.lower() for keyword in important_keywords):
            score += 3
        
        # Contains specifics (names, numbers, etc.)
        if re.search(r'[A-Z][a-z]+\s+[A-Z][a-z]+|\d+', sentence):
            score += 1
        
        scored_remaining.append((score, sentence))
    
    # Sort by score and add top sentences
    scored_remaining.sort(key=lambda x: x[0], reverse=True)
    
    for score, sentence in scored_remaining:
        if len(summary_points) >= 8:
            break
        if score >= 2:  # Only include reasonably important sentences
            clean_sentence = sentence[:120] + ("..." if len(sentence) > 120 else "")
            summary_points.append(f"• Key Content: {clean_sentence}")
    
    # If we still don't have enough points, add any remaining content
    if len(summary_points) < 4:
        for sentence in remaining_sentences[:4]:
            if len(summary_points) >= 6:
                break
            clean_sentence = sentence[:120] + ("..." if len(sentence) > 120 else "")
            summary_points.append(f"• Additional Information: {clean_sentence}")
    
    # Ensure we have a minimum number of summary points
    if len(summary_points) < 3:
        # Create summary from content chunks
        chunk_size = max(50, total_words // 6)
        for i in range(0, min(len(content_words), chunk_size * 4), chunk_size):
            if len(summary_points) >= 5:
                break
            chunk = ' '.join(content_words[i:i+chunk_size])
            if len(chunk) > 40:
                clean_chunk = chunk[:120] + ("..." if len(chunk) > 120 else "")
                summary_points.append(f"• Content Section {len(summary_points)+1}: {clean_chunk}")
    
    # Create final summary
    final_summary = '\n'.join(summary_points)
    
    # Ensure we have a proper summary
    if not summary_points or len(final_summary) < 30:
        final_summary = f"• Document Type: {total_words} word document processed\n• Content Status: Ready for review\n• Summary: {content[:150]}{'...' if len(content) > 150 else ''}"
    
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