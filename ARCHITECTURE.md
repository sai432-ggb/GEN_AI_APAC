# Synapse-Agent — Architecture Deep Dive

## 1. System Overview

Synapse-Agent is a **neuroadaptive generative AI** that uses simulated EEG (electroencephalogram) brainwave data to continuously tune the style, depth, and structure of AI-generated responses. The system is unique because:

1. **It reads cognitive state before every response** — not once at session start.
2. **It adapts silently** — the user never sees scores or mode labels unless they toggle Debug Mode.
3. **It runs persistently** — deployed to Google Cloud Run with `min-instances=1`, meaning the server is always warm.
4. **It is demonstrably novel** — no existing commercial AI product adapts to per-query cognitive load in real-time.

---

## 2. Component Breakdown

### 2.1 EEG / BCI Simulator (`NeuroSimulator` class in `app.py`)

Since physical EEG hardware is not connected, we synthesise realistic brainwave oscillations using overlapping sinusoidal functions with randomised Gaussian noise.

**Band physics:**

| Band | Frequency Range | Psychological Correlate | Simulation Formula |
|------|----------------|------------------------|--------------------|
| Alpha (α) | 8–12 Hz | Relaxation, idle, wakeful rest | `sin(t×0.10)×0.8 + sin(t×0.07)×0.3 + N(0, 0.25)` |
| Theta (θ) | 4–8 Hz | Creativity, drowsiness, memory | `cos(t×0.05)×0.7 + cos(t×0.03)×0.2 + N(0, 0.20)` |
| Beta (β) | 13–30 Hz | Active cognition, alertness, stress | `sin(t×0.50)×1.0 + sin(t×0.35)×0.5 + N(0.4, 1.10)` |

**Cognitive Load Index (CLI):**
```
CLI = clamp( β / (α + θ + ε) / 5.0, 0.0, 1.0 )
```
Where ε = 0.1 (division-by-zero guard). This is the Sterman-Mann engagement index.

**Threshold classification (SNN-style spike logic):**
```
CLI > 0.75  →  CRITICAL  (System 1 mode)
CLI < 0.35  →  LOW       (System 2 mode)
0.35–0.75   →  OPTIMAL   (Flow State)
```

The simulator runs in a **daemon thread** at 2 samples/second, maintaining a 200-sample rolling buffer.

---

### 2.2 MCP Server (`neuro_mcp_server.py`)

Built with **FastMCP** — a Python framework implementing Anthropic's Model Context Protocol. The MCP server exposes three tools:

- `read_cognitive_load()` — mandatory pre-query tool for the AI agent
- `get_cognitive_trend()` — returns 20-reading time-series for dashboards
- `reset_session()` — resets the EEG time counter

In the hosted Cloud Run deployment, the MCP logic is embedded directly in `app.py` for process efficiency. The standalone `neuro_mcp_server.py` is provided for external MCP clients (e.g., connecting Claude Desktop or other MCP-aware clients).

---

### 2.3 Flask API Server (`app.py`)

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serves `static/index.html` |
| GET | `/api/health` | Health probe for Cloud Run |
| GET | `/api/eeg/latest` | Single EEG reading (JSON) |
| GET | `/api/eeg/history?n=60` | Last N readings (JSON array) |
| GET | `/api/eeg/stream` | Server-Sent Events stream (500ms) |
| POST | `/api/chat` | Neuroadaptive chat endpoint |

**Chat flow:**
```
POST /api/chat  {message: "..."}
       ↓
  Read current EEG state (score, state, system)
       ↓
  Build SYSTEM_PROMPT_TEMPLATE with live cognitive data
       ↓
  Call Gemini 1.5 Pro via google-generativeai SDK
       ↓
  Return {reply, eeg, system_mode, demo_mode}
```

**Gunicorn config (production):**
- 1 worker (Cloud Run scales via container instances)
- 8 threads (handles SSE long-lived connections + API calls simultaneously)
- `timeout=0` (SSE streams must not time out)

---

### 2.4 Gemini 1.5 Pro Integration

The **neuroadaptive system prompt** is injected per-request — not as a static system prompt. This is intentional: each user message gets a fresh cognitive state reading baked into the prompt.

**System Prompt Template structure:**
```
You are Synapse-Agent — a neuroadaptive AI.

Current cognitive state:
  • Score: {score}
  • State: {state}
  • Mode:  System {system}

ADAPTIVE RULES:
  [IF CRITICAL] → System 1: short, bullets, bold, ≤12 words/sentence, ≤120 words
  [IF LOW]      → System 2: deep, analogies, Socratic, headers, ≥300 words
  [IF OPTIMAL]  → Flow: balanced, 150-250 words

User question: {user_query}
```

---

### 2.5 Frontend (`static/index.html`)

Single-file HTML/CSS/JS application with no build step required:

**Real-time components:**
- **Arc gauge** — SVG semicircle filled proportionally to CLI score
- **Oscilloscope** — HTML5 Canvas, draws the last 200 CLI samples as a waveform
- **Sparkline** — Canvas trend chart with threshold reference lines
- **Band bars** — CSS transition bars for α/θ/β amplitudes

**SSE connection:**
```javascript
const evtSource = new EventSource('/api/eeg/stream');
evtSource.onmessage = e => updateEEGUI(JSON.parse(e.data));
```
Reconnects automatically on failure.

**Flow diagram animation:** Each chat exchange triggers a staggered CSS animation across the 6-node pipeline diagram (EEG → MCP → Gemini → Adaptive Prompt → Response → User), showing judges exactly how data flows.

---

## 3. Deployment Architecture

### Cloud Run Configuration

```yaml
service: synapse-agent
region: us-central1        # free-tier eligible region
min-instances: 1            # NEVER cold-starts → always-on
max-instances: 3            # auto-scales under load
memory: 512Mi
cpu: 1
concurrency: 80             # requests per instance
timeout: 3600               # 1-hour max (for SSE connections)
```

**Why `min-instances=1` is critical:**
- Without it, Cloud Run scales to 0 after ~15 minutes of inactivity
- SSE streams would be severed on cold start
- Demo reliability requires zero cold-start latency

**Cost estimate (free tier):**
- 1 instance × 24h × 30 days = 720 instance-hours/month
- Free tier: 360,000 vCPU-seconds + 180,000 GB-seconds
- At 1 CPU + 512Mi: ~240 vCPU-hours free (≈ 10 days fully free)
- Remainder: ~$0.05/day (negligible)

### CI/CD Pipeline

```
git push origin main
       ↓
GitHub Actions: deploy.yml
       ↓
  1. Checkout source
  2. Authenticate to GCP (service account key)
  3. docker build → gcr.io/PROJECT/synapse-agent:SHA
  4. docker push
  5. gcloud run deploy (zero-downtime rolling update)
  6. Health check: GET /api/health
       ↓
Live URL updated automatically
```

---

## 4. Security Considerations

- `GEMINI_API_KEY` is injected via Cloud Run environment variables — never in code
- GitHub Secret `GCP_SA_KEY` has minimum IAM permissions (run.admin, storage.admin)
- Service Account key is single-use and should be rotated every 90 days
- No user data is persisted (stateless server)
- CORS enabled for development; restrict origin in production

---

## 5. Extension Roadmap

| Feature | Complexity | Impact |
|---------|-----------|--------|
| Real EEG via Muse headset (muse-lsl) | Medium | High |
| User session persistence (Firestore) | Low | Medium |
| Voice input / TTS output | Medium | High |
| Personalized baseline calibration | High | Very High |
| Multi-user classroom mode | High | High |
| Emotion detection via camera | High | Very High |
