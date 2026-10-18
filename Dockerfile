FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app
COPY . .
RUN mkdir -p local_data && chown -R app:app /app
USER app
EXPOSE 8766
CMD ["uvicorn", "rag_api:app", "--host", "0.0.0.0", "--port", "8766", "--workers", "1"]
