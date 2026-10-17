FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY services/data/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && useradd --system --uid 10001 --create-home appuser
COPY services/data /app/services/data
COPY services/shared /app/services/shared
RUN chmod -R a+rX /app
USER 10001:10001
EXPOSE 8000 9464
CMD ["uvicorn", "services.data.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
