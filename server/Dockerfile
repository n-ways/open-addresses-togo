# N-Ways Addressing for Togo: the registry server.
# Build from the repository root (docker compose does this): docker build -f server/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADDRESSES_DB=/data/addresses.sqlite \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

# The reference engine, the national border and the frozen area table it reads, the published registry, and the server.
COPY engine/reference/tg_engine.py engine/reference/plate_names.py engine/reference/border.py /app/engine/reference/
COPY engine/data/border.json /app/engine/data/border.json
COPY model/areas/areas.json /app/model/areas/areas.json
COPY model/units/keys.geojson model/units/cantons.geojson /app/model/units/
COPY registry /app/registry
COPY server/*.py /app/server/
COPY LICENSE LICENSE-DATA NOTICE /app/

RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin addresses \
    && mkdir -p /data && chown addresses /data

USER addresses
VOLUME ["/data"]
EXPOSE 8080

# The first start imports the bundled registry into the empty volume (about a minute), then serves.
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
    CMD ["python3", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/v1/health' % os.environ.get('PORT', '8080'), timeout=4)"]

CMD ["python3", "-m", "server", "serve", "--registry", "/app/registry"]
