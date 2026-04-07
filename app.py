"""
Synapse-Agent: Main Application Server
app.py

Flask web server that:
  1. Acts as an MCP Client → calls the Synapse-Neuro-Simulator tools
  2. Calls the Gemini 1.5 Pro API (Digital Cortex) with neuroadaptive prompting
  3. Exposes REST API endpoints consumed by the React/HTML frontend
  4. Streams EEG data for the real-time dashboard

Author: Synapse-Agent Project
License: MIT
"""

import os
import json
import math
import random
import time
import threading
from collections import deque
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# Configure Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# In-process EEG Simulator (mirrors neuro_mcp_server.py logic)
# This runs inside the same process so we don't need a separate MCP socket
# for the hosted demo — in production you'd wire the real MCP client here.
# ---------------------------------------------------------------------------

class NeuroSimulator:
    """Thread-safe EEG simulator that continuously generates samples."""

    def __init__(self):
        self._t      = 0.0
        self._lock   = threading.Lock()
        self._history: deque = deque(maxlen=200)
        self._running = False
        self._thread  = None

    # ------------------------------------------------------------------
    def _sample(self) -> dict:
        t = self._t
        alpha = abs(math.sin(t * 0.10) * 0.8 + math.sin(t * 0.07) * 0.3
                    + random.uniform(0.0, 0.25))
        theta = abs(math.cos(t * 0.05) * 0.7 + math.cos(t * 0.03) * 0.2
                    + random.uniform(0.0, 0.20))
        beta  = abs(math.sin(t * 0.50) * 1.0 + math.sin(t * 0.35) * 0.5
                    + random.uniform(0.4, 1.10))

        raw_load       = beta / (alpha + theta + 0.1)
        score          = round(min(max(raw_load / 5.0, 0.0), 1.0), 4)

        if score > 0.75:
            state, system, color = "CRITICAL", 1, "#ef4444"
        elif score < 0.35:
            state, system, color = "LOW",      2, "#3b82f6"
        else:
            state, system, color = "OPTIMAL",  0, "#22c55e"

        return {
            "cognitive_load_score": score,
            "neural_state":  state,
            "cognitive_system": system,
            "color": color,
            "bands": {"alpha": round(alpha,4), "theta": round(theta,4), "beta": round(beta,4)},
            "timestamp": round(time.time(), 3),
            "t": round(t, 2),
        }

    # ------------------------------------------------------------------
    def _loop(self):
        while self._running:
            with self._lock:
                self._t += 0.5          # advance time step
                sample = self._sample()
                self._history.append(sample)
            time.sleep(0.5)             # generate 2 samples/second

    # ------------------------------------------------------------------
    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False

    def latest(self) -> dict:
        with self._lock:
            return dict(self._history[-1]) if self._history else {}

    def history(self, n: int = 60) -> list:
        with self._lock:
            return list(self._history)[-n:]


neuro = NeuroSimulator()
neuro.start()


# ---------------------------------------------------------------------------
# System Prompt Builder
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_TEMPLATE = """
You are Synapse-Agent — a neuroadaptive AI tutor and assistant.

You have just read the user's real-time brainwave state:
  • Cognitive Load Score : {score}
  • Neural State         : {state}
  • Active Cognitive Mode: System {system}

ADAPTIVE RULES (follow them STRICTLY and SILENTLY — never mention EEG or scores):

[IF state == "CRITICAL" — Score > 0.75 — System 1]
• The user is overwhelmed. Think like Kahneman's "System 1" — fast, intuitive, effortless.
• Use ONLY short sentences (≤ 12 words each).
• Bullet points ONLY — no paragraphs.
• Bold the single most important action item.
• Vocabulary: grade-6 level. No jargon.
• Maximum response length: 120 words.

[IF state == "LOW" — Score < 0.35 — System 2]
• The user is under-stimulated and ready for depth. Think like "System 2" — slow, analytical.
• Provide rich, layered explanations with analogies and theoretical frameworks.
• Use Socratic questioning to deepen engagement.
• Include at least one surprising insight or counter-intuitive connection.
• Structure with clear headers. Minimum 300 words.

[IF state == "OPTIMAL" — Flow State]
• Provide a balanced, conversational response.
• Mix explanation with interactive elements (examples, light questions).
• 150-250 words.

User question: {user_query}
""".strip()


# ---------------------------------------------------------------------------
# Build Gemini model
# ---------------------------------------------------------------------------
def get_gemini_model():
    if not GEMINI_API_KEY:
        return None
    return genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        generation_config=genai.types.GenerationConfig(
            temperature=0.7,
            max_output_tokens=1024,
        ),
    )


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main frontend."""
    return send_from_directory("static", "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "Synapse-Agent", "version": "1.0.0"})


@app.route("/api/eeg/latest")
def eeg_latest():
    """Return the most recent EEG reading."""
    return jsonify(neuro.latest())


@app.route("/api/eeg/history")
def eeg_history():
    """Return the last N EEG readings (default 60)."""
    n = int(request.args.get("n", 60))
    return jsonify({"readings": neuro.history(n)})


@app.route("/api/eeg/stream")
def eeg_stream():
    """
    Server-Sent Events endpoint — pushes a new EEG sample every 500 ms.
    The frontend subscribes here to animate the live dashboard.
    """
    def generate():
        last_t = None
        while True:
            sample = neuro.latest()
            if sample and sample.get("t") != last_t:
                last_t = sample.get("t")
                yield f"data: {json.dumps(sample)}\n\n"
            time.sleep(0.5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Main chat endpoint.
    Body: { "message": "user question" }
    Response: { "reply": "...", "eeg": {...}, "system_mode": 0|1|2 }
    """
    body  = request.get_json(force=True)
    query = body.get("message", "").strip()

    if not query:
        return jsonify({"error": "message is required"}), 400

    # 1. Read live cognitive state
    eeg = neuro.latest()
    if not eeg:
        return jsonify({"error": "EEG simulator not ready"}), 503

    score  = eeg["cognitive_load_score"]
    state  = eeg["neural_state"]
    system = eeg["cognitive_system"]

    # 2. Build neuroadaptive prompt
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        score=score, state=state, system=system, user_query=query
    )

    # 3. Call Gemini (or fallback demo mode)
    if GEMINI_API_KEY:
        try:
            model  = get_gemini_model()
            result = model.generate_content(prompt)
            reply  = result.text
        except Exception as e:
            reply = f"[Gemini Error — Demo Mode] Score={score} | State={state}\n\n" \
                    f"(Would adapt response as System {system} mode)\n\nError: {e}"
    else:
        # Demo mode without API key — shows what the agent WOULD do
        reply = _demo_reply(query, score, state, system)

    return jsonify({
        "reply":       reply,
        "eeg":         eeg,
        "system_mode": system,
        "demo_mode":   not bool(GEMINI_API_KEY),
    })


def _demo_reply(query: str, score: float, state: str, system: int) -> str:
    """Fallback demo reply when no Gemini key is configured."""
    if system == 1:
        return (
            f"**[System 1 — Cognitive Overload Mode | Score: {score}]**\n\n"
            f"• Your question: *{query[:60]}*\n"
            f"• **Key action:** Simplify. Break it into steps.\n"
            f"• Rest. Then retry.\n\n"
            f"*(Set GEMINI_API_KEY for full AI responses)*"
        )
    elif system == 2:
        return (
            f"**[System 2 — Deep Thinking Mode | Score: {score}]**\n\n"
            f"Fascinating query: *{query}*\n\n"
            f"Let's examine this through multiple lenses. First, consider the foundational "
            f"premise — what assumptions underlie your question? Second, what would the "
            f"counter-argument look like? This Socratic approach reveals hidden structure...\n\n"
            f"*(Set GEMINI_API_KEY for full Gemini 1.5 Pro responses)*"
        )
    else:
        return (
            f"**[Flow State Mode | Score: {score}]**\n\n"
            f"Great question: *{query}*\n\n"
            f"Here's a balanced response. The Synapse-Agent is reading your cognitive state "
            f"in real-time and adapting accordingly. In Flow State, responses are clear, "
            f"conversational, and engaging.\n\n"
            f"*(Set GEMINI_API_KEY for full Gemini 1.5 Pro responses)*"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"🧠 Synapse-Agent starting on port {port} …")
    app.run(host="0.0.0.0", port=port, debug=debug)
