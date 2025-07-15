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
    """Generate a comprehensive bullet-point summary of the document"""
    if not content or len(content.strip()) == 0:
        return "• Document uploaded successfully\n• Content analysis completed\n• Ready for review"

    # Clean and prepare content
    content = content.strip()
    content_words = content.split()
    total_words = len(content_words)
    
    # Extract different types of information for comprehensive summary
    summary_points = []
    
    # 1. Document Overview/Purpose
    overview_keywords = ['overview', 'introduction', 'purpose', 'summary', 'document', 'report', 'memo', 'notice', 'policy']
    first_sentences = content.split('.')[:3]
    for sentence in first_sentences:
        sentence = sentence.strip()
        if len(sentence) > 20 and any(keyword in sentence.lower() for keyword in overview_keywords):
            summary_points.append(f"• Document Purpose: {sentence}")
            break
    
    if not summary_points:
        # Get first meaningful sentence as overview
        for sentence in content.split('.')[:5]:
            sentence = sentence.strip()
            if len(sentence) > 15 and len(sentence.split()) >= 5:
                summary_points.append(f"• Document Overview: {sentence}")
                break
    
    # 2. Key Actions/Requirements
    action_keywords = ['request', 'require', 'must', 'need', 'action', 'submit', 'approve', 'review', 'complete', 'deadline', 'urgent', 'immediate']
    action_sentences = []
    for sentence in content.split('.'):
        sentence = sentence.strip()
        if len(sentence) > 15 and any(keyword in sentence.lower() for keyword in action_keywords):
            action_sentences.append(sentence)
    
    if action_sentences:
        summary_points.append(f"• Key Actions Required: {action_sentences[0]}")
        if len(action_sentences) > 1:
            summary_points.append(f"• Additional Requirements: {action_sentences[1]}")
    
    # 3. Financial/Business Information
    financial_keywords = ['payment', 'invoice', 'cost', 'amount', 'budget', 'financial', 'money', 'price', 'revenue', 'expense']
    financial_info = []
    for sentence in content.split('.'):
        sentence = sentence.strip()
        if len(sentence) > 10 and any(keyword in sentence.lower() for keyword in financial_keywords):
            financial_info.append(sentence)
    
    if financial_info:
        summary_points.append(f"• Financial Details: {financial_info[0]}")
    
    # 4. People/Departments mentioned
    people_keywords = ['employee', 'manager', 'department', 'team', 'staff', 'director', 'supervisor', 'hr', 'finance', 'legal', 'it']
    people_info = []
    for sentence in content.split('.'):
        sentence = sentence.strip()
        if len(sentence) > 10 and any(keyword in sentence.lower() for keyword in people_keywords):
            people_info.append(sentence)
    
    if people_info:
        summary_points.append(f"• Departments/People Involved: {people_info[0]}")
    
    # 5. Dates/Timeline Information
    import re
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',  # DD Month YYYY
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}'  # Month DD, YYYY
    ]
    
    dates_found = []
    for pattern in date_patterns:
        dates_found.extend(re.findall(pattern, content, re.IGNORECASE))
    
    if dates_found:
        summary_points.append(f"• Important Dates: {', '.join(dates_found[:3])}")
    
    # 6. Process/Procedure Information
    process_keywords = ['process', 'procedure', 'workflow', 'step', 'guideline', 'instruction', 'method', 'approach']
    process_info = []
    for sentence in content.split('.'):
        sentence = sentence.strip()
        if len(sentence) > 15 and any(keyword in sentence.lower() for keyword in process_keywords):
            process_info.append(sentence)
    
    if process_info:
        summary_points.append(f"• Process Details: {process_info[0]}")
    
    # 7. Key Content Areas (extract most informative sentences)
    all_sentences = [s.strip() for s in content.split('.') if len(s.strip()) > 20]
    
    # Score sentences for informativeness
    scored_sentences = []
    for i, sentence in enumerate(all_sentences[:15]):
        score = 0
        words = sentence.split()
        
        # Length scoring
        if 8 <= len(words) <= 25:
            score += 3
        elif 6 <= len(words) <= 35:
            score += 2
        
        # Position scoring (earlier is better)
        if i < 3:
            score += 2
        elif i < 6:
            score += 1
        
        # Information density scoring
        if any(char.isdigit() for char in sentence):
            score += 1
        if sentence.count(',') > 1:  # Contains multiple clauses
            score += 1
        if any(word in sentence.lower() for word in ['important', 'key', 'critical', 'essential', 'main']):
            score += 2
            
        scored_sentences.append((score, sentence))
    
    # Sort by score and add top sentences not already covered
    scored_sentences.sort(key=lambda x: -x[0])
    
    # Add additional content points
    added_content = 0
    for score, sentence in scored_sentences:
        if added_content >= 3:  # Limit additional content points
            break
        # Check if this content is not already covered
        sentence_lower = sentence.lower()
        already_covered = False
        for existing_point in summary_points:
            existing_lower = existing_point.lower()
            common_words = set(sentence_lower.split()) & set(existing_lower.split())
            if len(common_words) > len(sentence_lower.split()) * 0.4:
                already_covered = True
                break
        
        if not already_covered and score > 2:
            summary_points.append(f"• Key Content: {sentence}")
            added_content += 1
    
    # 8. Document Status/Conclusion
    conclusion_keywords = ['conclusion', 'summary', 'result', 'outcome', 'decision', 'recommendation', 'next steps']
    last_sentences = content.split('.')[-3:]
    for sentence in reversed(last_sentences):
        sentence = sentence.strip()
        if len(sentence) > 15 and any(keyword in sentence.lower() for keyword in conclusion_keywords):
            summary_points.append(f"• Conclusion: {sentence}")
            break
    
    # Ensure we have a minimum number of points for comprehensive coverage
    if len(summary_points) < 3:
        # Add more general content points
        remaining_sentences = [s.strip() for s in content.split('.') if len(s.strip()) > 25]
        for sentence in remaining_sentences[:5]:
            if len(summary_points) >= 6:
                break
            # Check if not already covered
            sentence_lower = sentence.lower()
            already_covered = False
            for existing_point in summary_points:
                if any(word in existing_point.lower() for word in sentence_lower.split()[:3]):
                    already_covered = True
                    break
            
            if not already_covered:
                summary_points.append(f"• Content Detail: {sentence}")
    
    # Ensure we don't have too many points (limit to 8 for readability)
    if len(summary_points) > 8:
        summary_points = summary_points[:8]
    
    # If no points were generated, create basic summary from content
    if not summary_points:
        if total_words > 30:
            words_chunk1 = ' '.join(content_words[:20])
            words_chunk2 = ' '.join(content_words[20:40]) if len(content_words) > 20 else ""
            summary_points = [
                f"• Document Content: {words_chunk1}",
                f"• Additional Details: {words_chunk2}" if words_chunk2 else "• Document processing completed"
            ]
        else:
            summary_points = [
                f"• Document Content: {content}",
                "• Ready for review"
            ]
    
    # Join all points with newlines
    final_summary = '\n'.join(summary_points)
    
    # Ensure summary isn't too long
    if len(final_summary) > 800:
        # Truncate points to fit within limit
        truncated_points = []
        current_length = 0
        for point in summary_points:
            if current_length + len(point) + 1 <= 800:
                truncated_points.append(point)
                current_length += len(point) + 1
            else:
                break
        final_summary = '\n'.join(truncated_points)
    
    return final_summary if final_summary else "• Document processed and ready for review"

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