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
    """Generate a brief summary of the document"""
    sentences = [s.strip() for s in content.split('.') if s.strip()]

    if not sentences:
        return "No content available for summary"

    if len(sentences) <= 2:
        return content[:200] + "..." if len(content) > 200 else content

    # Find the most informative sentences (containing key terms)
    key_terms = ['request', 'document', 'policy', 'agreement', 'invoice', 'payment', 'employee', 'department', 'project', 'meeting', 'contract', 'budget', 'report', 'analysis', 'system', 'process']

    scored_sentences = []
    for sentence in sentences[:10]:  # Limit to first 10 sentences
        score = sum(1 for term in key_terms if term.lower() in sentence.lower())
        scored_sentences.append((score, sentence))

    # Sort by score and take top sentences
    scored_sentences.sort(key=lambda x: x[0], reverse=True)

    # Take top 2-3 sentences or first 2 if no high-scoring sentences
    if scored_sentences[0][0] > 0:
        summary_sentences = [s[1] for s in scored_sentences[:2]]
    else:
        summary_sentences = sentences[:2]

    summary = '. '.join(summary_sentences)
    if summary and not summary.endswith('.'):
        summary += '.'

    return summary[:400] + "..." if len(summary) > 400 else summary

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