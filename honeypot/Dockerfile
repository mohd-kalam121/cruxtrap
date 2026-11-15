# CruxTrap SSH honeypot. Build context: repository root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY honeypot/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin cruxtrap \
 && mkdir -p /app/data && chown cruxtrap:cruxtrap /app/data

COPY honeypot/ /app/honeypot/

USER cruxtrap
ENV HONEYPOT_HOST=0.0.0.0 \
    HONEYPOT_PORT=2222 \
    HONEYPOT_HOST_KEY=/app/data/ssh_host_key \
    QTABLE_PATH=/app/data/qtable.json
EXPOSE 2222

# Check the listening socket via /proc instead of connecting: a TCP probe would be logged
# as an attacker connection every interval.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import sys; sys.exit(0 if any(l.split()[1].endswith(':08AE') and l.split()[3] == '0A' for l in open('/proc/net/tcp').readlines()[1:]) else 1)"

CMD ["python", "-m", "honeypot"]
