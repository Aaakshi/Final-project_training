
import asyncio
import subprocess
import sys
import time
import signal
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import uvicorn

app = FastAPI(title="IDCR Demo Server")

# Global variable to track backend processes
backend_processes = []

# Mount static files
app.mount("/static", StaticFiles(directory="Final-project_training"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("Final-project_training/index.html")

@app.get("/health")
async def health_check():
    """Check if backend services are running"""
    services = {
        "api_gateway": "http://0.0.0.0:8000",
        "classification": "http://0.0.0.0:8001", 
        "routing_engine": "http://0.0.0.0:8002",
        "content_analysis": "http://0.0.0.0:8003",
        "workflow_integration": "http://0.0.0.0:8004"
    }
    
    status = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for service, url in services.items():
            try:
                response = await client.get(f"{url}/ping")
                status[service] = "healthy" if response.status_code == 200 else "unhealthy"
            except Exception as e:
                status[service] = f"offline: {str(e)}"
    
    return {"services": status}

@app.post("/api/classify")
async def classify_document():
    """Classify document through the processing pipeline"""
    try:
        # Simulate the full pipeline
        async with httpx.AsyncClient(timeout=10.0) as client:
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

def kill_existing_processes():
    """Kill any existing processes on our target ports"""
    ports_to_check = [8000, 8001, 8002, 8003, 8004]
    
    for port in ports_to_check:
        try:
            # Kill any existing processes on these ports
            subprocess.run([
                "pkill", "-f", f"port {port}"
            ], capture_output=True)
            
            subprocess.run([
                "pkill", "-f", f":{port}"
            ], capture_output=True)
            
            time.sleep(0.5)
        except Exception:
            pass
    
    print("Cleaned up existing processes")

def start_backend():
    """Start all microservices with proper error handling"""
    global backend_processes
    
    # Clean up any existing processes first
    kill_existing_processes()
    
    print("Starting backend microservices...")
    
    # Services with their paths and ports
    services = [
        ("Final-project_training/microservices/api_gateway/app", 8000),
        ("Final-project_training/microservices/classification/app", 8001),
        ("Final-project_training/microservices/routing_engine/app", 8002),
        ("Final-project_training/microservices/content_analysis/app", 8003),
        ("Final-project_training/microservices/workflow_integration/app", 8004)
    ]
    
    backend_processes = []
    
    for service_path, port in services:
        try:
            # Set up environment with proper Python path
            env = os.environ.copy()
            current_dir = os.getcwd()
            project_root = os.path.join(current_dir, "Final-project_training")
            env['PYTHONPATH'] = f"{project_root}:{env.get('PYTHONPATH', '')}"
            
            # Start the service
            process = subprocess.Popen([
                sys.executable, "-m", "uvicorn", "main:app", 
                "--host", "0.0.0.0", 
                "--port", str(port), 
                "--log-level", "error",  # Reduce log noise
                "--access-log"
            ], 
            cwd=service_path, 
            env=env,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group
            )
            
            backend_processes.append(process)
            print(f"✓ Started {service_path.split('/')[-1]} service on port {port}")
            time.sleep(1.5)  # Give each service time to start
            
        except Exception as e:
            print(f"✗ Failed to start service {service_path}: {e}")
    
    return backend_processes

def cleanup_processes():
    """Clean up all backend processes"""
    global backend_processes
    
    print("\nShutting down backend services...")
    
    for process in backend_processes:
        try:
            # Kill the entire process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except:
            try:
                process.terminate()
            except:
                pass
    
    # Wait for processes to terminate
    time.sleep(2)
    
    # Force kill if needed
    for process in backend_processes:
        try:
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except:
            try:
                process.kill()
            except:
                pass
    
    backend_processes = []
    print("Backend services stopped")

async def wait_for_services():
    """Wait for backend services to be ready"""
    print("Waiting for backend services to be ready...")
    
    services = [
        "http://0.0.0.0:8000/ping",
        "http://0.0.0.0:8001/ping", 
        "http://0.0.0.0:8002/ping",
        "http://0.0.0.0:8003/ping",
        "http://0.0.0.0:8004/ping"
    ]
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        ready_services = 0
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            for service_url in services:
                try:
                    response = await client.get(service_url)
                    if response.status_code == 200:
                        ready_services += 1
                except:
                    pass
        
        if ready_services == len(services):
            print("✓ All backend services are ready!")
            return True
        
        print(f"  {ready_services}/{len(services)} services ready...")
        await asyncio.sleep(1)
        retry_count += 1
    
    print("⚠ Some services may not be ready, but continuing...")
    return False

@app.on_event("shutdown")
def shutdown_event():
    cleanup_processes()

if __name__ == "__main__":
    # Handle shutdown gracefully
    def signal_handler(sig, frame):
        cleanup_processes()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start backend services
        print("🚀 Starting IDCR Demo Application")
        print("=" * 50)
        
        backend_processes = start_backend()
        
        # Wait for services to be ready
        asyncio.run(wait_for_services())
        
        print("\n🌐 Starting frontend server...")
        print("=" * 50)
        print("📱 Access your application at: http://0.0.0.0:5000")
        print("🔍 Backend services running on ports 8000-8004")
        print("⚡ Ready to process documents!")
        print("=" * 50)
        
        # Start the demo frontend server on port 5000
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=5000,
            access_log=True,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        cleanup_processes()
    except Exception as e:
        print(f"Error starting application: {e}")
        cleanup_processes()
