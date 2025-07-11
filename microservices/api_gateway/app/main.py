from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import ping

app = FastAPI(title="API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ping.router, prefix="/ping", tags=["ping"])

@app.on_event("startup")
async def startup_event():
    from libs.utils.logger import setup_logger
    logger = setup_logger(__name__)
    logger.info("API Gateway started")