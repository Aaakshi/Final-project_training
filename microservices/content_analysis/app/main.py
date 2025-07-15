
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os
import uvicorn
import re
from typing import List, Dict, Any

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

class EntityExtractionResult(BaseModel):
    names: List[str]
    dates: List[str]
    amounts: List[str]
    emails: List[str]
    phone_numbers: List[str]

class AnalysisResponse(BaseModel):
    entities: EntityExtractionResult
    sentiment: str
    summary: str
    key_phrases: List[str]
    readability_score: float
    risk_score: float
    metadata: Dict[str, Any]

@app.get("/")
async def root():
    return {"message": "Content Analysis Service is running", "service": "content_analysis"}

def generate_summary(content: str) -> str:
    """Generate a comprehensive bullet-point summary that covers the entire document"""
    if not content or len(content.strip()) == 0:
        return "• Document uploaded successfully\n• Content analysis completed\n• Ready for review"

    # Clean and prepare content
    content = content.strip().replace('\r\n', '\n').replace('\r', '\n')
    content_words = content.split()
    total_words = len(content_words)
    
    if total_words < 10:
        return f"• Short document with {total_words} words\n• Content: {content[:100]}{'...' if len(content) > 100 else ''}\n• Ready for review"

    # Split content into meaningful sentences
    sentences = []
    
    # Enhanced sentence splitting
    sentence_endings = re.split(r'[.!?]+', content)
    
    for sent in sentence_endings:
        sent = sent.strip()
        # Filter out very short or meaningless sentences
        if len(sent) > 15 and len(sent.split()) >= 4:
            sentences.append(sent)
    
    # If we don't have enough sentences, try splitting by line breaks
    if len(sentences) < 3:
        line_sentences = content.split('\n')
        for sent in line_sentences:
            sent = sent.strip()
            if len(sent) > 15 and len(sent.split()) >= 4:
                sentences.append(sent)
    
    # Last resort: create chunks from the content
    if len(sentences) < 3:
        words = content.split()
        chunk_size = max(15, len(words) // 6)
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            if len(chunk) > 20:
                sentences.append(chunk)

    summary_points = []
    used_sentences = set()
    content_lower = content.lower()
    
    # Strategy 1: Document Overview from beginning (25% of content)
    beginning_section = content[:len(content)//4]
    if sentences and len(sentences) > 0:
        first_sentence = sentences[0][:150] + ("..." if len(sentences[0]) > 150 else "")
        summary_points.append(f"• Document Overview: {first_sentence}")
        used_sentences.add(sentences[0])
    
    # Strategy 2: Extract action items and requirements
    action_keywords = ['must', 'required', 'need', 'should', 'request', 'action', 'submit', 'complete', 'deadline', 'due', 'urgent', 'immediate', 'approve', 'review', 'apply', 'process', 'respond', 'reply', 'contact']
    action_count = 0
    
    for sentence in sentences:
        if sentence not in used_sentences and action_count < 2:
            if any(keyword in sentence.lower() for keyword in action_keywords):
                clean_sentence = sentence[:150] + ("..." if len(sentence) > 150 else "")
                summary_points.append(f"• Action Required: {clean_sentence}")
                used_sentences.add(sentence)
                action_count += 1
    
    # Strategy 3: Financial and numerical information
    financial_keywords = ['cost', 'price', 'amount', 'budget', 'payment', 'invoice', 'expense', 'revenue', 'salary', 'fee', 'charge', 'dollar', 'money', 'fund', 'bill', 'receipt', 'account']
    financial_count = 0
    
    for sentence in sentences:
        if sentence not in used_sentences and financial_count < 1:
            has_financial = any(keyword in sentence.lower() for keyword in financial_keywords)
            has_numbers = re.search(r'\$\d+|\d+\.\d+|\d+%|\d+,\d+|\d+ dollars?', sentence)
            if has_financial or has_numbers:
                clean_sentence = sentence[:150] + ("..." if len(sentence) > 150 else "")
                summary_points.append(f"• Financial Details: {clean_sentence}")
                used_sentences.add(sentence)
                financial_count += 1
    
    # Strategy 4: Personnel and department information
    people_keywords = ['employee', 'manager', 'director', 'supervisor', 'team', 'department', 'hr', 'finance', 'legal', 'it', 'staff', 'personnel', 'admin', 'coordinator', 'specialist']
    people_count = 0
    
    for sentence in sentences:
        if sentence not in used_sentences and people_count < 1:
            if any(keyword in sentence.lower() for keyword in people_keywords):
                clean_sentence = sentence[:150] + ("..." if len(sentence) > 150 else "")
                summary_points.append(f"• Personnel/Department: {clean_sentence}")
                used_sentences.add(sentence)
                people_count += 1
    
    # Strategy 5: Timeline and dates
    date_patterns = [r'\d{4}-\d{2}-\d{2}', r'\d{2}/\d{2}/\d{4}', r'\d{2}-\d{2}-\d{4}']
    timeline_keywords = ['deadline', 'due', 'schedule', 'date', 'time', 'when', 'by', 'until', 'before', 'after', 'start', 'end', 'meeting', 'event']
    timeline_count = 0
    
    for sentence in sentences:
        if sentence not in used_sentences and timeline_count < 1:
            has_date = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in date_patterns)
            has_timeline = any(keyword in sentence.lower() for keyword in timeline_keywords)
            if has_date or has_timeline:
                clean_sentence = sentence[:150] + ("..." if len(sentence) > 150 else "")
                summary_points.append(f"• Timeline/Dates: {clean_sentence}")
                used_sentences.add(sentence)
                timeline_count += 1

    # Strategy 6: Process and procedures from middle section (50% of content)
    middle_start = len(content) // 4
    middle_end = 3 * len(content) // 4
    middle_section = content[middle_start:middle_end]
    
    process_keywords = ['process', 'procedure', 'step', 'method', 'workflow', 'protocol', 'guideline', 'instruction', 'policy', 'rule']
    process_count = 0
    
    for sentence in sentences:
        if sentence not in used_sentences and process_count < 2:
            sentence_position = content.find(sentence)
            if middle_start <= sentence_position <= middle_end:
                if any(keyword in sentence.lower() for keyword in process_keywords) or len(sentence.split()) > 10:
                    clean_sentence = sentence[:150] + ("..." if len(sentence) > 150 else "")
                    summary_points.append(f"• Process/Procedure: {clean_sentence}")
                    used_sentences.add(sentence)
                    process_count += 1

    # Strategy 7: Key content from remaining sentences
    remaining_sentences = [s for s in sentences if s not in used_sentences]
    
    # Score remaining sentences by importance
    scored_remaining = []
    for sentence in remaining_sentences:
        score = 0
        words = sentence.split()
        
        # Prefer medium-length sentences
        if 8 <= len(words) <= 25:
            score += 2
        
        # Important keywords
        important_keywords = ['important', 'critical', 'key', 'main', 'primary', 'significant', 'essential', 'note', 'attention', 'summary', 'conclusion']
        if any(keyword in sentence.lower() for keyword in important_keywords):
            score += 3
        
        # Contains specifics (names, numbers, etc.)
        if re.search(r'[A-Z][a-z]+\s+[A-Z][a-z]+|\d+', sentence):
            score += 1
        
        # Avoid very generic sentences
        generic_phrases = ['this document', 'please note', 'thank you', 'sincerely', 'best regards']
        if any(phrase in sentence.lower() for phrase in generic_phrases):
            score -= 2
        
        scored_remaining.append((score, sentence))
    
    # Sort by score and add top sentences
    scored_remaining.sort(key=lambda x: x[0], reverse=True)
    
    content_added = 0
    for score, sentence in scored_remaining:
        if len(summary_points) >= 10:
            break
        if score >= 1 and content_added < 3:
            clean_sentence = sentence[:150] + ("..." if len(sentence) > 150 else "")
            summary_points.append(f"• Key Content: {clean_sentence}")
            content_added += 1

    # Strategy 8: Ensure minimum coverage - add from final 25% if needed
    if len(summary_points) < 4:
        final_section = content[3 * len(content) // 4:]
        final_sentences = [s for s in sentences if s not in used_sentences and final_section in content[content.find(s):]]
        
        for sentence in final_sentences[:2]:
            if len(summary_points) >= 8:
                break
            clean_sentence = sentence[:150] + ("..." if len(sentence) > 150 else "")
            summary_points.append(f"• Document Conclusion: {clean_sentence}")

    # Ensure we have a minimum number of summary points
    if len(summary_points) < 3:
        # Create summary from content chunks to ensure coverage
        chunk_size = max(30, total_words // 8)
        for i in range(0, min(len(content_words), chunk_size * 6), chunk_size):
            if len(summary_points) >= 6:
                break
            chunk = ' '.join(content_words[i:i+chunk_size])
            if len(chunk) > 30:
                clean_chunk = chunk[:150] + ("..." if len(chunk) > 150 else "")
                summary_points.append(f"• Content Section: {clean_chunk}")
    
    # Create final summary
    final_summary = '\n'.join(summary_points)
    
    # Ensure we have a proper summary
    if not summary_points or len(final_summary) < 50:
        final_summary = f"• Document processed: {total_words} words analyzed\n• Content type: Text document\n• Key content: {content[:200]}{'...' if len(content) > 200 else ''}\n• Analysis complete: Ready for review"
    
    # Ensure at least 15% coverage as mentioned in requirements
    coverage_target = max(3, min(10, total_words // 50))
    while len(summary_points) < coverage_target and len(summary_points) < 10:
        if remaining_sentences:
            sentence = remaining_sentences.pop(0)
            clean_sentence = sentence[:150] + ("..." if len(sentence) > 150 else "")
            summary_points.append(f"• Additional Information: {clean_sentence}")
        else:
            break
    
    return '\n'.join(summary_points)

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
        r'\(\d{3}\)\s*\d{3}-\d{4}',  # (123) 456-7890
        r'\d{3}-\d{3}-\d{4}',  # 123-456-7890
        r'\d{3}\.\d{3}\.\d{4}',  # 123.456.7890
        r'\+\d{1,3}\s*\d{3}\s*\d{3}\s*\d{4}'  # +1 123 456 7890
    ]
    phone_numbers = []
    for pattern in phone_patterns:
        phone_numbers.extend(re.findall(pattern, content))
    phone_numbers = list(set(phone_numbers))

    return EntityExtractionResult(
        names=names[:10],  # Limit to top 10
        dates=dates[:10],
        amounts=amounts[:10],
        emails=emails[:10],
        phone_numbers=phone_numbers[:10]
    )

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

    # Common stop words to exclude
    stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use', 'may', 'than', 'first', 'been', 'call', 'find', 'from', 'have', 'into', 'long', 'look', 'made', 'make', 'many', 'more', 'most', 'move', 'much', 'must', 'name', 'need', 'number', 'other', 'over', 'part', 'people', 'place', 'right', 'said', 'same', 'seem', 'some', 'sound', 'still', 'such', 'take', 'tell', 'them', 'these', 'they', 'this', 'time', 'very', 'want', 'water', 'well', 'were', 'what', 'when', 'where', 'which', 'while', 'will', 'with', 'word', 'work', 'would', 'write', 'year', 'your'}

    for word in words:
        if word not in stop_words and len(word) > 3:
            word_freq[word] = word_freq.get(word, 0) + 1

    # Get top words
    key_phrases = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:15]
    return [phrase[0] for phrase in key_phrases]

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

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_content(request: AnalysisRequest):
    """Analyze document content and return comprehensive analysis"""
    try:
        # Extract entities
        entities = extract_entities(request.content)
        
        # Generate comprehensive summary
        summary = generate_summary(request.content)
        
        # Extract key phrases
        key_phrases = extract_key_phrases(request.content)
        
        # Calculate readability score
        readability_score = calculate_readability_score(request.content)
        
        # Calculate risk score
        risk_score = calculate_risk_score(request.content, entities)
        
        # Basic sentiment analysis (simplified)
        sentiment = "neutral"
        positive_words = ["good", "excellent", "positive", "success", "approve", "great"]
        negative_words = ["bad", "terrible", "negative", "fail", "reject", "poor"]
        
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
            "character_count": len(request.content),
            "sentence_count": len(request.content.split('.')),
            "paragraph_count": len(request.content.split('\n\n'))
        }
        
        logger.info(f"Analyzed content for document {request.doc_id}")
        
        return AnalysisResponse(
            entities=entities,
            sentiment=sentiment,
            summary=summary,
            key_phrases=key_phrases,
            readability_score=readability_score,
            risk_score=risk_score,
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Content analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/ping")
async def ping():
    return {"message": "pong from Content Analysis Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
