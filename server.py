"""
Agent Status Service
--------------------
A lightweight FastAPI service exposing:
  - GET  /status   → latest status + context
  - POST /status   → update status + context
  - GET  /message  → latest agent message
  - POST /message  → post a markdown message (auto-resets status to pending)
  - GET  /history  → unified status + message history
  - GET  /         → browser UI

Run with:
    pip install fastapi uvicorn
    python server.py"""

from __future__ import annotations

import uvicorn
from datetime import datetime, timezone
import os
import sys
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

StatusLiteral = Literal["pending", "success", "failure"]

_current: dict = {
    "status": "pending",
    "context": "",
    "timestamp": datetime.now(timezone.utc).isoformat(),
}
_current_message: dict | None = None
# Unified history — each entry has a "type" key: "status" | "message"
_history: list[dict] = []

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Agent Status Service", version="1.0.0")

# PyInstaller extracts to a temp folder _MEIPASS; resolve the correct path for static assets
base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
assets_dir = os.path.join(base_dir, "assets")
app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class StatusPayload(BaseModel):
    status: StatusLiteral
    context: str = ""


class MessagePayload(BaseModel):
    message: str  # markdown content


class StatusResponse(BaseModel):
    status: str
    context: str
    timestamp: str
    last_updated: str  # alias for agent polling convenience
    retry_after: int = 5  # suggested polling interval in seconds


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/status", response_model=StatusResponse)
def get_status():
    """Return the latest status and context."""
    return StatusResponse(
        status=_current["status"],
        context=_current["context"],
        timestamp=_current["timestamp"],
        last_updated=_current["timestamp"],
    )


@app.post("/status", response_model=StatusResponse, status_code=201)
def post_status(payload: StatusPayload):
    """Update the status and context."""
    ts = datetime.now(timezone.utc).isoformat()
    _history.append({**_current, "type": "status"})
    _current["status"] = payload.status
    _current["context"] = payload.context
    _current["timestamp"] = ts
    return StatusResponse(
        status=_current["status"],
        context=_current["context"],
        timestamp=ts,
        last_updated=ts,
    )


@app.get("/message")
def get_message():
    """Return the latest agent message, or null fields if none yet."""
    if _current_message is None:
        return {"message": None, "timestamp": None}
    return _current_message


@app.post("/message", status_code=201)
def post_message(payload: MessagePayload):
    """Accept a markdown message from the agent and reset status to pending."""
    global _current_message
    ts = datetime.now(timezone.utc).isoformat()
    # Snapshot current status into history before resetting
    _history.append({**_current, "type": "status"})
    # Reset status to pending so the agent won't re-read stale user context
    _current["status"] = "pending"
    _current["timestamp"] = ts
    # Store the message
    _current_message = {"message": payload.message, "timestamp": ts}
    _history.append({"type": "message", "message": payload.message, "timestamp": ts})
    return _current_message


@app.get("/history")
def get_history():
    """Return the full unified history (status + message entries, oldest first)."""
    return {"history": _history}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Agent Status Dashboard</title>
<link id="favicon" rel="icon" type="image/png" href="/assets/icon.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #0d0f14;
    --surface:  #161a22;
    --surface2: #1e2330;
    --border:   #2a3040;
    --accent:   #5b8af0;
    --accent2:  #7c5bf0;
    --pending:  #f0c040;
    --success:  #40d97f;
    --failure:  #f05555;
    --text:     #e8ecf5;
    --muted:    #7a839a;
    --radius:   12px;
    --glow:     0 0 24px rgba(91,138,240,0.18);
  }

  body {
    font-family: 'Inter', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 2rem 1rem;
  }

  .container { max-width: 760px; margin: 0 auto; }

  /* Header */
  header {
    display: flex; align-items: center; gap: 1rem;
    margin-bottom: 2rem;
  }
  .logo {
    width: 44px; height: 44px; border-radius: 10px;
    overflow: hidden; flex-shrink: 0;
    box-shadow: var(--glow);
  }
  .logo img { width: 100%; height: 100%; object-fit: cover; display: block; }
  header h1 { font-size: 1.4rem; font-weight: 700; }
  header p  { color: var(--muted); font-size: 0.85rem; margin-top: 2px; }

  /* Current status banner */
  .banner {
    display: flex; align-items: center; gap: 1rem;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 1.2rem 1.5rem;
    margin-bottom: 1.5rem; transition: border-color 0.4s;
    box-shadow: var(--glow);
  }
  .pill {
    padding: 4px 14px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .pill.pending { background: rgba(240,192,64,0.15); color: var(--pending); border: 1px solid var(--pending); }
  .pill.success { background: rgba(64,217,127,0.15); color: var(--success); border: 1px solid var(--success); }
  .pill.failure { background: rgba(240,85,85,0.15);  color: var(--failure); border: 1px solid var(--failure); }

  .banner-meta { flex: 1; }
  .banner-context { font-size: 0.9rem; color: var(--text); margin-top: 4px; word-break: break-word; }
  .banner-ts { font-size: 0.75rem; color: var(--muted); margin-top: 6px; }

  .live-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--success); margin-left: auto; flex-shrink: 0;
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%,100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.4; transform: scale(0.75); }
  }

  /* Card */
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 1.5rem;
    margin-bottom: 1.5rem;
  }
  .card h2 { font-size: 0.9rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 1rem; }

  /* Form */
  .field { margin-bottom: 1rem; }
  label { display: block; font-size: 0.82rem; color: var(--muted); margin-bottom: 6px; font-weight: 500; }

  select, textarea {
    width: 100%; background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); font-family: inherit;
    font-size: 0.9rem; padding: 0.65rem 0.9rem;
    transition: border-color 0.2s, box-shadow 0.2s; resize: vertical;
    appearance: none; outline: none;
  }
  select:focus, textarea:focus {
    border-color: var(--accent); box-shadow: 0 0 0 3px rgba(91,138,240,0.15);
  }
  textarea { min-height: 90px; }

  button {
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: #fff; border: none; border-radius: 8px; cursor: pointer;
    font-family: inherit; font-size: 0.9rem; font-weight: 600;
    padding: 0.65rem 1.4rem; transition: opacity 0.2s, transform 0.1s;
    box-shadow: var(--glow);
  }
  button:hover   { opacity: 0.9; }
  button:active  { transform: scale(0.97); }
  button:disabled { opacity: 0.5; cursor: not-allowed; }

  .msg {
    display: none; margin-top: 0.75rem; padding: 0.6rem 1rem;
    border-radius: 8px; font-size: 0.85rem;
  }
  .msg.ok  { background: rgba(64,217,127,0.12); color: var(--success); border: 1px solid var(--success); display: block; }
  .msg.err { background: rgba(240,85,85,0.12);  color: var(--failure); border: 1px solid var(--failure);  display: block; }

  /* Agent message panel */
  .msg-panel {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 1.5rem;
    margin-bottom: 1.5rem;
    background-image: linear-gradient(135deg, rgba(91,138,240,0.06) 0%, rgba(64,217,127,0.04) 100%);
    display: none; /* hidden until a message exists */
  }
  .msg-panel-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 1rem;
  }
  .msg-panel-header h2 {
    font-size: 0.9rem; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.08em;
  }
  .msg-tag {
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.07em;
    text-transform: uppercase; padding: 3px 10px; border-radius: 999px;
    color: var(--accent); background: rgba(91,138,240,0.12);
    border: 1px solid rgba(91,138,240,0.35);
    animation: pulse 2.5s ease-in-out infinite;
  }
  .msg-body {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; padding: 1rem 1.2rem;
    font-size: 0.9rem; line-height: 1.7; color: var(--text);
  }
  /* Markdown styles inside .msg-body */
  .msg-body h1,.msg-body h2,.msg-body h3 { font-weight: 600; margin: 0.75rem 0 0.35rem; color: var(--text); }
  .msg-body h1 { font-size: 1.1rem; } .msg-body h2 { font-size: 1rem; } .msg-body h3 { font-size: 0.95rem; }
  .msg-body p  { margin: 0.4rem 0; }
  .msg-body ul, .msg-body ol { margin: 0.4rem 0 0.4rem 1.4rem; }
  .msg-body li { margin-bottom: 0.2rem; }
  .msg-body code {
    background: rgba(91,138,240,0.12); color: var(--accent);
    border-radius: 4px; padding: 1px 5px; font-size: 0.85em; font-family: monospace;
  }
  .msg-body pre {
    background: rgba(0,0,0,0.3); border: 1px solid var(--border);
    border-radius: 6px; padding: 0.75rem 1rem; overflow-x: auto; margin: 0.5rem 0;
  }
  .msg-body pre code { background: none; padding: 0; color: var(--text); }
  .msg-body blockquote {
    border-left: 3px solid var(--accent); margin: 0.5rem 0;
    padding: 0.25rem 0.75rem; color: var(--muted);
  }
  .msg-ts { font-size: 0.72rem; color: var(--muted); margin-top: 0.6rem; }

  /* History */
  .history-list { list-style: none; display: flex; flex-direction: column; gap: 0.75rem; }
  .hitem {
    display: flex; gap: 0.9rem; align-items: flex-start;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 10px; padding: 0.9rem 1.1rem;
    animation: fadeIn 0.3s ease;
  }
  .hitem.hitem-msg {
    border-color: rgba(91,138,240,0.3);
    background: rgba(91,138,240,0.04);
  }
  @keyframes fadeIn { from { opacity:0; transform: translateY(6px); } to { opacity:1; } }
  .hitem-badge {
    flex-shrink: 0; padding: 4px 10px; border-radius: 999px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--accent); background: rgba(91,138,240,0.12); border: 1px solid rgba(91,138,240,0.35);
  }
  .hitem-body { flex: 1; min-width: 0; }
  .hitem-context { font-size: 0.88rem; margin-top: 4px; color: var(--muted); word-break: break-word; }
  /* markdown inside history message items */
  .hitem-md { font-size: 0.85rem; margin-top: 4px; color: var(--muted); word-break: break-word; line-height: 1.55; }
  .hitem-md p { margin: 0.2rem 0; }
  .hitem-md code { background: rgba(91,138,240,0.1); color: var(--accent); border-radius: 3px; padding: 0 4px; font-size: 0.82em; font-family: monospace; }
  .hitem-ts { font-size: 0.72rem; color: var(--muted); margin-top: 4px; }
  .empty { color: var(--muted); font-size: 0.88rem; text-align: center; padding: 1.5rem 0; }

  /* API hint */
  .api-hint {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 1rem 1.2rem;
    font-size: 0.8rem; color: var(--muted);
    display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem;
  }
  .api-hint code { color: var(--accent); font-family: monospace; }

  /* Agent prompt card */
  .prompt-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 1.5rem;
    margin-bottom: 1.5rem;
    background-image: linear-gradient(135deg, rgba(91,138,240,0.05) 0%, rgba(124,91,240,0.05) 100%);
  }
  .prompt-card-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 1rem;
  }
  .prompt-card-header h2 {
    font-size: 0.9rem; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.08em;
  }
  .prompt-label {
    display: inline-flex; align-items: center; gap: 0.3rem;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--accent2); background: rgba(124,91,240,0.12);
    border: 1px solid rgba(124,91,240,0.35);
    padding: 3px 10px; border-radius: 999px;
  }
  .prompt-body {
    position: relative;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; padding: 1rem 1.1rem;
  }
  .prompt-body pre {
    font-family: 'Inter', sans-serif; font-size: 0.875rem;
    color: var(--text); white-space: pre-wrap; word-break: break-word;
    line-height: 1.6; margin: 0;
  }
  .copy-btn {
    position: absolute; top: 0.6rem; right: 0.6rem;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--muted); cursor: pointer;
    font-family: inherit; font-size: 0.75rem; font-weight: 500;
    padding: 4px 10px; transition: color 0.2s, border-color 0.2s, background 0.2s;
    box-shadow: none;
  }
  .copy-btn:hover { color: var(--accent); border-color: var(--accent); background: var(--surface2); }
  .copy-btn.copied { color: var(--success); border-color: var(--success); }
</style>
</head>
<body>
<div class="container">

  <header>
    <div class="logo"><img src="/assets/icon.png" alt="statusgate icon" /></div>
    <div>
      <h1>Agent Status Dashboard</h1>
      <p>Live status board for iterative agent workflows</p>
    </div>
  </header>

  <!-- Current status -->
  <div class="banner" id="banner">
    <div class="pill pending" id="statusPill">pending</div>
    <div class="banner-meta">
      <div class="banner-context" id="bannerCtx">—</div>
      <div class="banner-ts" id="bannerTs"></div>
    </div>
    <div class="live-dot" title="Live polling active"></div>
  </div>

  <!-- Update form -->
  <div class="card">
    <h2>Update Status</h2>
    <div class="field">
      <label for="statusSel">Status</label>
      <select id="statusSel">
        <option value="pending">⏳ Pending</option>
        <option value="success">✅ Success</option>
        <option value="failure">❌ Failure</option>
      </select>
    </div>
    <div class="field">
      <label for="ctxInput">Context / Notes</label>
      <textarea id="ctxInput" placeholder="Describe what happened, paste logs, etc."></textarea>
    </div>
    <button id="submitBtn" onclick="postStatus()">Submit Update</button>
    <div class="msg" id="formMsg"></div>
  </div>

  <!-- Agent message panel (shown only when a message exists) -->
  <div class="msg-panel" id="msgPanel">
    <div class="msg-panel-header">
      <h2>Agent Message</h2>
      <span class="msg-tag">🤖 New</span>
    </div>
    <div class="msg-body" id="msgBody"></div>
    <div class="msg-ts" id="msgTs"></div>
  </div>

  <!-- History -->
  <div class="card">
    <h2>Activity log</h2>
    <ul class="history-list" id="historyList">
      <li class="empty">No previous updates.</li>
    </ul>
  </div>

  <!-- Agent prompt -->
  <div class="prompt-card">
    <div class="prompt-card-header">
      <h2>Agent Prompt</h2>
      <span class="prompt-label">🤖 Copy &amp; paste into your agent</span>
    </div>
    <div class="prompt-body">
      <button class="copy-btn" id="copyBtn" onclick="copyPrompt()">Copy</button>
      <pre id="agentPrompt">Monitor the API at http://localhost:8000/status continuously until a success status is returned.

Rules:
  - If status is "pending", wait 10 seconds and poll again.
  - If status is "failure", read the context field and apply the corrective measures described in it.
    After applying the fix, post a progress update:
      POST http://localhost:8000/message
      Content-Type: application/json
      {"message": "# Update...Describe what you did/what you need..."} (markdown supported)
    This will automatically reset the status to pending. Then resume polling every 10 seconds.
  - Do NOT call POST /status yourself — only the human operator sets the status.
  - Repeat this loop indefinitely until the API returns success.
  - Only stop when success is confirmed from the API.</pre>
    </div>
  </div>

  <!-- API hint -->
  <div class="api-hint">
    <span><code>GET /status</code> → latest JSON</span>
    <span><code>POST /status</code> → update (body: <code>{"status","context"}</code>)</span>
    <span><code>POST /message</code> → agent markdown message → resets to pending</span>
    <span><code>GET /history</code> → unified activity log</span>
    <span><code>retry-after: 5s</code> suggested polling interval</span>
  </div>

</div>

<script>
const fmtTs = iso => iso ? new Date(iso).toLocaleString() : '';

function copyPrompt() {
  const text = document.getElementById('agentPrompt').textContent;
  const btn = document.getElementById('copyBtn');
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = '✓ Copied';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
  }).catch(() => {
    // Fallback for older browsers
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    btn.textContent = '✓ Copied'; btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
  });
}

function pillClass(s) { return ['pending','success','failure'].includes(s) ? s : 'pending'; }

let lastServerStatus = null;

async function fetchStatus() {
  try {
    const r = await fetch('/status');
    if (!r.ok) return;
    const d = await r.json();
    const pill = document.getElementById('statusPill');
    pill.textContent = d.status;
    pill.className = 'pill ' + pillClass(d.status);
    document.getElementById('bannerCtx').textContent = d.context || '—';
    document.getElementById('bannerTs').textContent = 'Last updated: ' + fmtTs(d.timestamp);
    
    if (lastServerStatus !== d.status) {
      document.getElementById('statusSel').value = d.status;
      lastServerStatus = d.status;
    }
  } catch(e) {}
}

async function fetchMessage() {
  try {
    const r = await fetch('/message');
    if (!r.ok) return;
    const d = await r.json();
    const panel = document.getElementById('msgPanel');
    const favicon = document.getElementById('favicon');
    if (!d.message) {
      panel.style.display = 'none';
      favicon.href = '/assets/icon.png';
      return;
    }
    panel.style.display = 'block';
    favicon.href = '/assets/icon_ready.png';
    document.getElementById('msgBody').innerHTML = marked.parse(d.message);
    document.getElementById('msgTs').textContent = 'Received: ' + fmtTs(d.timestamp);
  } catch(e) {}
}

async function fetchHistory() {
  try {
    const r = await fetch('/history');
    if (!r.ok) return;
    const d = await r.json();
    const list = document.getElementById('historyList');
    if (!d.history || d.history.length === 0) {
      list.innerHTML = '<li class="empty">No previous updates.</li>';
      return;
    }
    list.innerHTML = [...d.history].reverse().map(h => {
      if (h.type === 'message') {
        return `
        <li class="hitem hitem-msg">
          <span class="hitem-badge">🤖 Agent</span>
          <div class="hitem-body">
            <div class="hitem-md">${marked.parse(h.message)}</div>
            <div class="hitem-ts">${fmtTs(h.timestamp)}</div>
          </div>
        </li>`;
      }
      return `
      <li class="hitem">
        <div class="pill ${pillClass(h.status)}">${h.status}</div>
        <div class="hitem-body">
          <div class="hitem-context">${h.context || '<em>no context</em>'}</div>
          <div class="hitem-ts">${fmtTs(h.timestamp)}</div>
        </div>
      </li>`;
    }).join('');
  } catch(e) {}
}

async function postStatus() {
  const btn  = document.getElementById('submitBtn');
  const msg  = document.getElementById('formMsg');
  const status  = document.getElementById('statusSel').value;
  const context = document.getElementById('ctxInput').value.trim();
  btn.disabled = true;
  msg.className = 'msg';
  try {
    const r = await fetch('/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, context })
    });
    if (!r.ok) throw new Error('Server error ' + r.status);
    msg.textContent = '✓ Status updated successfully.';
    msg.className = 'msg ok';
    document.getElementById('ctxInput').value = '';
    document.getElementById('favicon').href = '/assets/icon.png';
    await Promise.all([fetchStatus(), fetchHistory()]);
  } catch(e) {
    msg.textContent = '✗ ' + e.message;
    msg.className = 'msg err';
  } finally {
    btn.disabled = false;
    setTimeout(() => msg.className = 'msg', 4000);
  }
}

// Initial load + poll every 5s
fetchStatus();
fetchMessage();
fetchHistory();
setInterval(() => { fetchStatus(); fetchMessage(); fetchHistory(); }, 5000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def ui():
    return HTML


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
