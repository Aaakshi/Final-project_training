
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import re

app = FastAPI(title="Content Analysis Service")

class AnalysisRequest(BaseModel):
    doc_id: str
    content: str

@app.get("/ping")
async def ping():
    return {"message": "pong from Content Analysis Service"}

@app.post("/analyze")
async def analyze_content(request: AnalysisRequest):
    """Analyze document content for entities and metadata"""
    content = request.content
    
    # Extract entities using simple regex patterns
    
    # Find names (capitalized words)
    names = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', content)
    
    # Find dates
    dates = re.findall(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}', content)
    
    # Find emails
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
    
    # Find amounts/currency
    amounts = re.findall(r'\$\d+(?:,\d{3})*(?:\.\d{2})?|\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP)', content)
    
    # Calculate risk score based on content
    risk_score = 0.0
    if any(word in content.lower() for word in ['confidential', 'private', 'sensitive']):
        risk_score += 0.3
    if any(word in content.lower() for word in ['contract', 'agreement', 'legal']):
        risk_score += 0.2
    if amounts:
        risk_score += 0.2
    
    risk_score = min(risk_score, 1.0)
    
    return {
        "doc_id": request.doc_id,
        "entities": {
            "names": names,
            "dates": dates,
            "emails": emails,
            "amounts": amounts
        },
        "risk_score": risk_score,
        "word_count": len(content.split()),
        "analysis_status": "completed"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
