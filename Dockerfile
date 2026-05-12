FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y build-essential python3-dev && \
    pip install -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
