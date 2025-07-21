FROM python:3.11-slim

WORKDIR /app

COPY app/user-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/user-service/src/ /app/src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"] 