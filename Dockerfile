# ════════════════════════════════════════════════════════════
#  Synapse-Agent — Dockerfile
#  Target: Google Cloud Run (free tier, always-on min-instances=1)
#  Base:   python:3.12-slim (small image = faster cold starts)
# ════════════════════════════════════════════════════════════

FROM python:3.12-slim

# Metadata
LABEL maintainer="synapse-agent"
LABEL description="Neuroadaptive AI Agent — EEG-Simulated Cognitive Load Adaptation"

# ── System dependencies ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ──
WORKDIR /app

# ── Python dependencies (cached layer) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──
COPY . .

# ── Cloud Run listens on $PORT (default 8080) ──
ENV PORT=8080
EXPOSE 8080

# ── Health check ──
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/health || exit 1

# ── Start with Gunicorn (production WSGI server) ──
#    --workers 1        → single worker (Cloud Run scales via instances)
#    --threads 8        → multi-thread to handle SSE + API simultaneously
#    --timeout 0        → disable timeout for SSE long-lived connections
#    --bind 0.0.0.0:$PORT
CMD exec gunicorn app:app \
    --workers 1 \
    --threads 8 \
    --timeout 0 \
    --bind 0.0.0.0:${PORT} \
    --access-logfile - \
    --error-logfile - \
    --log-level info
