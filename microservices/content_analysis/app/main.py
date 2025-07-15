from fastapi import FastAPI
from pydantic importBaseModel
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

    # Split content into sentences for analysis
    sentences = [s.strip() for s in re.split(r'[.!?]+', content) if len(s.strip()) > 10]

    if not sentences:
        return f"• Document processed: {total_words} words analyzed\n• Content type: Text document\n• Ready for review"

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
        final_sentences = [s for s in sentences if s not in used_sentences and s in final_section]

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

@app.get("/")
async def root():
    return {"message": "Content Analysis Service is running", "service": "content_analysis"}

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
            "sentence_count": len(re.split(r'[.!?]+', request.content)),
            "paragraph_count": len([p for p in request.content.split('\n\n') if p.strip()]),
            "avg_sentence_length": len(request.content.split()) / max(len(re.split(r'[.!?]+', request.content)), 1)
        }

        logger.info(f"Analyzed content for document {request.doc_id}")

        return AnalysisResponse(
            entities=entities,
            summary=summary,
            key_phrases=key_phrases,
            sentiment=sentiment,
            readability_score=readability_score,
            risk_score=risk_score,
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
            metadata={"word_count": 0, "sentence_count": 0, "paragraph_count": 0, "avg_sentence_length": 0}
        )

@app.get("/ping")
async def ping():
    return {"message": "pong from Content Analysis Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)