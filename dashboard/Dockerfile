# CruxTrap SOC dashboard. Build context: repository root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY dashboard/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin cruxtrap

COPY dashboard/ /app/dashboard/

USER cruxtrap
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"

CMD ["uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
