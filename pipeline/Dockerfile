# CruxTrap pipeline. Build context: repository root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY pipeline/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin cruxtrap

COPY pipeline/ /app/pipeline/
COPY db/init.sql /app/db/init.sql

USER cruxtrap
ENV SCHEMA_PATH=/app/db/init.sql \
    GEOIP_DB=/app/geoip/GeoLite2-City.mmdb

CMD ["python", "-m", "pipeline"]
