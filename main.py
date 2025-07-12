
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import asyncio
import subprocess
import os
import uvicorn

app = FastAPI(title="IDCR Demo Server")

# Mount static files
app.mount("/static", StaticFiles(directory="Final-project_training"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("Final-project_training/index.html")

@app.get("/health")
async def health_check():
    """Check if backend services are running"""
    services = {
        "api_gateway": "http://localhost:8000",
        "classification": "http://localhost:8001", 
        "routing_engine": "http://localhost:8002",
        "content_analysis": "http://localhost:8003",
        "workflow_integration": "http://localhost:8004"
    }
    
    status = {}
    async with httpx.AsyncClient() as client:
        for service, url in services.items():
            try:
                response = await client.get(f"{url}/ping", timeout=2.0)
                status[service] = "healthy" if response.status_code == 200 else "unhealthy"
            except:
                status[service] = "offline"
    
    return {"services": status}

@app.post("/api/classify")
async def classify_document():
    """Classify document through the processing pipeline"""
    try:
        # Simulate the full pipeline
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. Classify document
            classify_response = await client.post(
                "http://0.0.0.0:8001/classify",
                files={"file": ("document.txt", b"This is an invoice for $1000", "text/plain")}
            )
            
            if classify_response.status_code != 200:
                return {"error": "Classification service unavailable"}
            
            classification = classify_response.json()
            
            # 2. Route document
            route_response = await client.post(
                "http://0.0.0.0:8002/route",
                json={"doc_id": "doc-123", "doc_type": classification["doc_type"]}
            )
            
            if route_response.status_code != 200:
                return {"error": "Routing service unavailable"}
            
            routing = route_response.json()
            
            # 3. Analyze content
            analysis_response = await client.post(
                "http://0.0.0.0:8003/analyze",
                json={"doc_id": "doc-123", "content": "This is an invoice for $1000"}
            )
            
            if analysis_response.status_code != 200:
                return {"error": "Analysis service unavailable"}
            
            analysis = analysis_response.json()
            
            # 4. Send notification
            notify_response = await client.post(
                "http://0.0.0.0:8004/notify",
                json={"doc_id": "doc-123", "assignee": routing["assignee"]}
            )
            
            if notify_response.status_code != 200:
                return {"error": "Notification service unavailable"}
            
            notification = notify_response.json()
            
            return {
                "success": True,
                "results": {
                    "classification": classification,
                    "routing": routing,
                    "analysis": analysis,
                    "notification": notification
                }
            }
            
    except Exception as e:
        return {"error": f"Pipeline failed: {str(e)}"}

def start_backend():
    """Start all microservices"""
    print("Starting backend microservices...")
    
    # Change to the project directory
    os.chdir("Final-project_training")
    
    # Start individual Python services directly
    services = [
        ("microservices/api_gateway/app", 8000),
        ("microservices/classification/app", 8001),
        ("microservices/routing_engine/app", 8002),
        ("microservices/content_analysis/app", 8003),
        ("microservices/workflow_integration/app", 8004)
    ]
    
    for service_path, port in services:
        try:
            subprocess.Popen([
                "python", "-m", "uvicorn", "main:app", 
                "--host", "0.0.0.0", "--port", str(port)
            ], cwd=service_path)
            print(f"Started service at {service_path} on port {port}")
        except Exception as e:
            print(f"Failed to start service {service_path}: {e}")

if __name__ == "__main__":
    # Start backend services
    start_backend()
    
    # Wait a moment for services to start
    print("Waiting for services to initialize...")
    asyncio.run(asyncio.sleep(5))
    
    # Start the demo frontend server
    print("Starting demo frontend server on http://0.0.0.0:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000)
