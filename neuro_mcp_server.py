"""
Synapse-Agent: Real-Time BCI (Brain-Computer Interface) Simulator
MCP Server — neuro_mcp_server.py

Simulates EEG brainwave data to compute Cognitive Load using the engagement
ratio: Beta / (Alpha + Theta). Exposes the result as an MCP tool so any
MCP-compatible client (Gemini, Claude, etc.) can call it.

Author: Synapse-Agent Project
License: MIT
"""

from mcp.server.fastmcp import FastMCP
import random
import time
import math
import json

# ---------------------------------------------------------------------------
# MCP Server Initialization
# ---------------------------------------------------------------------------
mcp = FastMCP("Synapse-Neuro-Simulator")

# Internal state — simulates continuous brainwave oscillation over time
_current_time: float = 0.0
_session_history: list[dict] = []   # keeps last 100 readings for trend analysis


# ---------------------------------------------------------------------------
# Helper: compute one EEG sample
# ---------------------------------------------------------------------------
def _compute_eeg_sample(t: float) -> dict:
    """
    Synthesise Alpha, Theta and Beta band amplitudes using overlapping sine
    waves with randomised noise — mimicking real EEG spectral patterns.

    Returns a dict with raw band values, computed load score and neural state.
    """
    # Alpha (8-12 Hz): relaxation / idle — slow oscillation
    alpha = abs(math.sin(t * 0.10) * 0.8 + math.sin(t * 0.07) * 0.3
                + random.uniform(0.0, 0.25))

    # Theta (4-8 Hz): creativity / drowsiness — very slow
    theta = abs(math.cos(t * 0.05) * 0.7 + math.cos(t * 0.03) * 0.2
                + random.uniform(0.0, 0.20))

    # Beta (13-30 Hz): active thinking / stress — fast, higher amplitude
    beta  = abs(math.sin(t * 0.50) * 1.0 + math.sin(t * 0.35) * 0.5
                + random.uniform(0.4, 1.10))

    # Engagement / Cognitive Load Ratio (Sterman & Mann, 1994 formulation)
    raw_load = beta / (alpha + theta + 0.1)   # +0.1 guards div-by-zero

    # Normalise to [0.0, 1.0]
    normalized_load = round(min(max(raw_load / 5.0, 0.0), 1.0), 4)

    # Classify neural state using SNN-style threshold spikes
    if normalized_load > 0.75:
        state   = "CRITICAL"
        label   = "Cognitive Overload — System 1 Mode (Fast / Simple)"
        emoji   = "🔴"
        system  = 1
    elif normalized_load < 0.35:
        state   = "LOW"
        label   = "Under-stimulated — System 2 Mode (Deep / Deliberate)"
        emoji   = "🔵"
        system  = 2
    else:
        state   = "OPTIMAL"
        label   = "Flow State — Balanced Interaction"
        emoji   = "🟢"
        system  = 0

    return {
        "cognitive_load_score": normalized_load,
        "neural_state":  state,
        "state_label":   label,
        "emoji":         emoji,
        "cognitive_system": system,
        "bands": {
            "alpha": round(alpha, 4),
            "theta": round(theta, 4),
            "beta":  round(beta,  4),
        },
        "timestamp": round(t, 2),
    }


# ---------------------------------------------------------------------------
# MCP Tool 1: read_cognitive_load  (primary tool used by the AI agent)
# ---------------------------------------------------------------------------
@mcp.tool()
def read_cognitive_load() -> str:
    """
    Simulates real-time EEG brainwave processing and returns a normalised
    cognitive load score between 0.0 (Relaxed) and 1.0 (Overloaded).

    The AI agent MUST call this tool before answering every user query.
    The returned JSON drives the neuroadaptive response style.
    """
    global _current_time, _session_history

    _current_time += 1.0
    sample = _compute_eeg_sample(_current_time)

    # Maintain rolling history
    _session_history.append(sample)
    if len(_session_history) > 100:
        _session_history.pop(0)

    return json.dumps(sample)


# ---------------------------------------------------------------------------
# MCP Tool 2: get_cognitive_trend  (optional — for dashboard/debug mode)
# ---------------------------------------------------------------------------
@mcp.tool()
def get_cognitive_trend() -> str:
    """
    Returns the last 20 cognitive-load readings as a time-series array.
    Useful for rendering the real-time EEG graph on the frontend dashboard.
    """
    recent = _session_history[-20:] if len(_session_history) >= 20 else _session_history
    return json.dumps({
        "count": len(recent),
        "readings": recent,
        "average_load": round(
            sum(r["cognitive_load_score"] for r in recent) / max(len(recent), 1), 4
        ),
    })


# ---------------------------------------------------------------------------
# MCP Tool 3: reset_session  (optional utility)
# ---------------------------------------------------------------------------
@mcp.tool()
def reset_session() -> str:
    """Resets the internal EEG time counter and session history."""
    global _current_time, _session_history
    _current_time   = 0.0
    _session_history = []
    return json.dumps({"status": "reset", "message": "EEG session cleared."})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("🧠 Synapse-Neuro-Simulator MCP Server starting …")
    mcp.run()
