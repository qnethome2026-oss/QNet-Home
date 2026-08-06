FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY services/iq9_voice_router/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services /app/services
COPY agent /app/agent
CMD ["python", "-m", "services.iq9_voice_router.main"]
