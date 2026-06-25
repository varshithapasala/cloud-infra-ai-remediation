FROM python:3.12-slim

WORKDIR /app

COPY remediation_agent/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY remediation_agent ./remediation_agent

CMD ["python", "-m", "remediation_agent.main"]