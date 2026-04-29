FROM python:3.12-slim

WORKDIR /app

RUN addgroup --system xmonitors && adduser --system --ingroup xmonitors xmonitors

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY xmonitors ./xmonitors
COPY config.example.json ./config.example.json

RUN mkdir -p /app/data && chown -R xmonitors:xmonitors /app
USER xmonitors

HEALTHCHECK --interval=60s --timeout=10s CMD python -m xmonitors --once --dry-run --config /app/config.json || exit 1

CMD ["python", "-m", "xmonitors", "--config", "/app/config.json"]
