FROM python:3.12-slim

WORKDIR /app

COPY incident_api/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY incident_api ./incident_api

CMD ["uvicorn", "incident_api.main:app", "--host", "0.0.0.0", "--port", "8080"]