FROM python:3.9-slim
WORKDIR /app
COPY microservices/classification/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
COPY microservices/classification/app/ ./app/
COPY libs/ ./libs/
ENV PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]