
from fastapi import FastAPI, File, UploadFile, HTTPException
import uvicorn
import tempfile
import os

app = FastAPI(title="Classification Service")

@app.get("/ping")
async def ping():
    return {"message": "pong from Classification Service"}

@app.post("/classify")
async def classify_document(file: UploadFile = File(...)):
    """Classify uploaded document"""
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        # Extract text based on file type
        extracted_text = ""
        if file.content_type == "text/plain":
            with open(tmp_file_path, 'r', encoding='utf-8') as f:
                extracted_text = f.read()
        elif file.content_type == "application/pdf":
            try:
                import PyPDF2
                with open(tmp_file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        extracted_text += page.extract_text()
            except:
                extracted_text = "PDF text extraction failed"
        
        # Simple classification logic
        text_lower = extracted_text.lower()
        
        if any(word in text_lower for word in ['invoice', 'bill', 'payment', 'amount', 'total']):
            doc_type = "invoice"
            department = "finance"
            priority = "high"
            confidence = 0.85
        elif any(word in text_lower for word in ['contract', 'agreement', 'legal', 'terms']):
            doc_type = "contract"
            department = "legal"
            priority = "high"
            confidence = 0.90
        elif any(word in text_lower for word in ['report', 'analysis', 'summary', 'findings']):
            doc_type = "report"
            department = "general"
            priority = "medium"
            confidence = 0.75
        elif any(word in text_lower for word in ['employee', 'hr', 'human resources', 'personnel']):
            doc_type = "hr_document"
            department = "hr"
            priority = "medium"
            confidence = 0.80
        else:
            doc_type = "general"
            department = "general"
            priority = "low"
            confidence = 0.60

        # Clean up temp file
        os.unlink(tmp_file_path)

        return {
            "doc_type": doc_type,
            "department": department,
            "priority": priority,
            "confidence": confidence,
            "extracted_text": extracted_text[:500],  # First 500 chars
            "page_count": 1,
            "language": "en",
            "tags": [doc_type, department]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
