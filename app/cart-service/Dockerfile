FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create profiles directory
RUN mkdir -p /app/profiles

COPY app/cart-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/cart-service/src/ /app/src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"] 