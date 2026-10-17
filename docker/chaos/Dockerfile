FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/chaos
COPY docker/chaos/supervisor.py /opt/chaos/supervisor.py
ENTRYPOINT ["python", "/opt/chaos/supervisor.py"]
CMD ["serve"]
