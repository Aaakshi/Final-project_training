
from fastapi import FastAPI
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from libs.utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

app = FastAPI(title="API Gateway")

@app.get("/ping")
async def ping():
    return {"message": "pong from API Gateway"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "api_gateway"}
