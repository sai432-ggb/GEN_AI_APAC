# 🧠 Synapse-Agent — Neuroadaptive Generative AI

> **The world's first AI assistant that reads your cognitive load in real-time and adapts every response to your brain's current capacity.**

[![Deploy to Cloud Run](https://img.shields.io/badge/Deploy-Cloud%20Run-4285F4?logo=google-cloud&logoColor=white)](https://console.cloud.google.com/run)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Gemini 1.5 Pro](https://img.shields.io/badge/AI-Gemini%201.5%20Pro-orange?logo=google)](https://ai.google.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📌 What Is Synapse-Agent?

Synapse-Agent is a **neuroadaptive generative AI** that simulates reading your real-time EEG brainwave data using a Brain-Computer Interface (BCI) Simulator exposed via the **Model Context Protocol (MCP)**. The core AI — Gemini 1.5 Pro — uses this cognitive state data to **dynamically shift its response style** between two cognitive modes inspired by Daniel Kahneman's dual-process theory:

| Mode | Trigger | Behaviour |
|------|---------|-----------|
| **System 1** 🔴 | Cognitive Overload (score > 0.75) | Short sentences, bullets, simple vocabulary, bold actions |
| **Flow State** 🟢 | Optimal (0.35–0.75) | Balanced, conversational, engaging |
| **System 2** 🔵 | Under-stimulated (score < 0.35) | Deep dives, analogies, Socratic questioning, 300+ words |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     USER'S BROWSER                          │
│  React-like HTML frontend with:                             │
│  • Live EEG oscilloscope (Canvas)                           │
│  • Cognitive load arc gauge                                 │
│  • Brainwave band bars (Alpha/Theta/Beta)                   │
│  • System 1/2/Flow mode indicator                           │
│  • Real-time chat UI with adaptive responses                │
│  • Debug mode toggle (shows raw EEG JSON)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP + Server-Sent Events (SSE)
┌──────────────────────▼──────────────────────────────────────┐
│              FLASK WEB SERVER  (app.py)                     │
│  • /api/eeg/stream   → SSE stream (500ms cadence)          │
│  • /api/eeg/latest   → latest EEG reading                  │
│  • /api/chat         → neuroadaptive chat endpoint          │
│  • /api/health       → Cloud Run health probe              │
└────────┬────────────────────────────┬───────────────────────┘
         │                            │
┌────────▼────────┐        ┌──────────▼────────────────────────┐
│  NEURO SIM      │        │   GEMINI 1.5 PRO (Digital Cortex) │
│  (In-process    │        │   System Prompt:                   │
│   EEG thread)   │        │   • Reads cognitive_load_score     │
│                 │        │   • Selects System 1 / 2 / Flow   │
│  Alpha β sin(t) │        │   • Adapts vocabulary, length,     │
│  Theta β cos(t) │        │     structure, depth               │
│  Beta  β sin(5t)│        │   • Never reveals EEG data to user │
│                 │        │                                     │
│  Score = Beta / │        │   google-generativeai SDK          │
│  (Alpha+Theta)  │        └───────────────────────────────────┘
└─────────────────┘
         │
┌────────▼────────────────────────────────────────────────────┐
│         MCP SERVER (neuro_mcp_server.py)                    │
│         FastMCP — standalone if needed for external clients │
│  Tools:                                                     │
│  • read_cognitive_load()  → primary tool                   │
│  • get_cognitive_trend()  → last 20 readings               │
│  • reset_session()        → reset EEG state                │
└─────────────────────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────────────────┐
│         GOOGLE CLOUD RUN  (always-on, free tier)           │
│         min-instances=1  →  server NEVER sleeps            │
│         Gunicorn  1 worker  8 threads  timeout=0           │
│         Auto-deploys via GitHub Actions on push to main    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Project Structure

```
synapse-agent/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD: auto-deploy to Cloud Run
│
├── backend/
│   ├── app.py                  # Flask server + Gemini integration
│   ├── neuro_mcp_server.py     # Standalone MCP BCI Simulator
│   ├── requirements.txt        # Python dependencies
│   ├── Dockerfile              # Container definition
│   ├── .dockerignore
│   └── static/
│       └── index.html          # Full frontend (HTML/CSS/JS)
│
├── docs/
│   └── ARCHITECTURE.md         # Deep-dive architecture doc
│
├── .env.example                # Environment variable template
├── .gitignore
└── README.md                   # ← You are here
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- A **Gemini API key** — get one free at [aistudio.google.com](https://aistudio.google.com/app/apikey)
- Git

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/synapse-agent.git
cd synapse-agent
```

### 2. Create virtual environment & install dependencies
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set environment variables
```bash
cp ../.env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here
```

### 4. Run the server
```bash
python app.py
```

Open your browser at **http://localhost:8080** — the EEG dashboard starts immediately!

> **No API key?** The app runs in **Demo Mode** — the EEG simulator, oscilloscope, and dashboard all work; AI responses show what System 1/2/Flow mode would generate.

---

## ☁️ Deploy to Google Cloud Run (Free Tier — Always-On)

Cloud Run's **free tier** gives you:
- 2 million requests/month free
- 360,000 vCPU-seconds/month free
- 180,000 GB-seconds memory/month free

With `min-instances=1`, your server **never stops** even with zero traffic.

### Step 1 — Google Cloud Setup (one-time)

```bash
# Install gcloud CLI: https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login

# Create a new project (or use existing)
gcloud projects create synapse-agent-demo --name="Synapse Agent"
gcloud config set project synapse-agent-demo

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Set compute region (free tier region)
gcloud config set run/region us-central1
```

### Step 2 — Build & Deploy (manual first deploy)

```bash
cd backend

# Build the Docker image and push to Google Container Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/synapse-agent

# Deploy to Cloud Run with always-on (min-instances=1)
gcloud run deploy synapse-agent \
  --image gcr.io/YOUR_PROJECT_ID/synapse-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 3 \
  --concurrency 80 \
  --timeout 3600 \
  --set-env-vars "GEMINI_API_KEY=your_gemini_key_here"
```

Cloud Run will output a **live HTTPS URL** — that's your permanent demo link!

### Step 3 — GitHub Actions Auto-Deploy (CI/CD)

Set these **GitHub Secrets** in your repo → Settings → Secrets → Actions:

| Secret | Value |
|--------|-------|
| `GCP_PROJECT_ID` | Your GCP project ID (e.g., `synapse-agent-demo`) |
| `GCP_SA_KEY` | JSON key of a GCP Service Account (see below) |
| `GEMINI_API_KEY` | Your Gemini API key |

**Create the Service Account:**
```bash
# Create SA
gcloud iam service-accounts create github-deploy \
  --display-name="GitHub Actions Deploy"

# Grant roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Download key (paste contents into GCP_SA_KEY GitHub secret)
gcloud iam service-accounts keys create key.json \
  --iam-account=github-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com

cat key.json   # copy this entire JSON into GCP_SA_KEY secret
rm key.json    # delete the local key file immediately
```

**After setup:** Every `git push` to `main` automatically rebuilds and redeploys!

---

## 🔬 How the EEG Simulation Works

The `NeuroSimulator` generates continuous synthetic brainwave data using overlapping sine/cosine functions:

```python
alpha = abs(sin(t × 0.10) × 0.8 + sin(t × 0.07) × 0.3 + noise(0, 0.25))
theta = abs(cos(t × 0.05) × 0.7 + cos(t × 0.03) × 0.2 + noise(0, 0.20))
beta  = abs(sin(t × 0.50) × 1.0 + sin(t × 0.35) × 0.5 + noise(0.4, 1.10))

cognitive_load = clamp(beta / (alpha + theta + 0.1) / 5.0, 0.0, 1.0)
```

This mimics the **Sterman-Mann engagement index** used in real neurofeedback systems. The β/(α+θ) ratio is a validated proxy for mental workload widely used in BCI research.

---

## 🎮 Debug Mode

Click the **DEBUG** toggle in the top-right corner to reveal:
- Raw EEG JSON payload (all band values, scores, timestamps)
- Live fluctuating cognitive_load_score
- Neural state transitions in real-time

This is designed for **hackathon demos** — judges can see the SNN-style "spikes" triggering the AI's System 1/2 mode switches.

---

## 🧩 MCP Server (Standalone)

The `neuro_mcp_server.py` can also run as a **standalone MCP server** for any MCP-compatible client:

```bash
cd backend
python neuro_mcp_server.py
```

Available MCP tools:
- `read_cognitive_load()` — primary tool, returns score + state
- `get_cognitive_trend()` — last 20 readings time-series
- `reset_session()` — reset EEG timer

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m 'Add feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- **Daniel Kahneman** — Thinking, Fast and Slow (System 1/2 framework)
- **Sterman & Mann (1994)** — EEG engagement index formulation
- **Google** — Gemini 1.5 Pro & Cloud Run free tier
- **Anthropic** — Model Context Protocol (MCP) specification
#   G E N _ A I _ A P A C  
 