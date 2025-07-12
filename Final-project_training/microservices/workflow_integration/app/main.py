from fastapi import FastAPI
from pydantic import BaseModel
from libs.utils.logger import setup_logger
import pika

app = FastAPI(title="Workflow Integration Service")
logger = setup_logger(__name__)

class NotificationRequest(BaseModel):
    doc_id: str
    assignee: str

@app.post("/notify")
async def send_notification(request: NotificationRequest):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='notifications')
    message = f"Document {request.doc_id} assigned to {request.assignee}"
    channel.basic_publish(exchange='', routing_key='notifications', body=message)
    connection.close()
    logger.info(f"Sent notification for document {request.doc_id}")
    return {"status": "notification sent"}

@app.get("/ping")
async def ping():
    return {"message": "pong from Workflow Integration Service"}