"""ClaimsPilot — Gradio UI.

Upload a claim (PDF/TXT) or pick a generated sample → live step-by-step agent
execution log → final decision, letter, and full audit trail.

Prereq: agents running (python scripts/start_agents.py).
Run:    python ui/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gradio as gr
from pypdf import PdfReader

from orchestrator.pipeline import ClaimsOrchestrator, StepEvent

CLAIMS_DIR = Path(__file__).resolve().parent.parent / "data" / "claims"

orchestrator = ClaimsOrchestrator()

STATUS_ICONS = {"started": "⏳", "completed": "✅", "failed": "❌"}
DECISION_BANNERS = {
    "approve": "## ✅ APPROVED",
    "reject": "## ❌ REJECTED",
    "escalate": "## ⚠️ ESCALATED to senior adjuster",
    "error": "## 💥 Pipeline error",
}


def read_document(file_path: str | None, sample_name: str | None) -> str:
    if file_path:
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        return path.read_text(encoding="utf-8", errors="replace")
    if sample_name:
        return (CLAIMS_DIR / sample_name).read_text(encoding="utf-8")
    raise gr.Error("Upload a claim document or choose a sample.")


def list_samples() -> list[str]:
    if CLAIMS_DIR.exists():
        return sorted(p.name for p in CLAIMS_DIR.glob("claim_*.txt"))
    return []


def process(file_path, sample_name):
    text = read_document(file_path, sample_name)

    log_lines: list[str] = ["**Agent execution log**", ""]

    def render_log() -> str:
        return "\n".join(log_lines)

    # discovery handshake first — shows the Agent Cards in the log
    try:
        cards = orchestrator.discover()
        for name, info in cards.items():
            log_lines.append(f"🔎 discovered `{name}` — {info}")
    except Exception as exc:
        raise gr.Error(
            f"Agent discovery failed ({exc}). Start the agents first: "
            "`python scripts/start_agents.py`"
        )
    yield render_log(), gr.skip(), gr.skip(), gr.skip()

    events: list[StepEvent] = []

    def on_event(event: StepEvent) -> None:
        events.append(event)

    result = None
    import threading

    done = threading.Event()

    def worker():
        nonlocal result
        result = orchestrator.run(text, on_event=on_event)
        done.set()

    threading.Thread(target=worker, daemon=True).start()

    shown = 0
    while not done.wait(timeout=0.3):
        while shown < len(events):
            event = events[shown]
            suffix = f" ({event.elapsed_s}s)" if event.elapsed_s else ""
            log_lines.append(f"{STATUS_ICONS[event.status]} **{event.agent}** {event.status}: {event.detail}{suffix}")
            shown += 1
        yield render_log(), gr.skip(), gr.skip(), gr.skip()
    while shown < len(events):
        event = events[shown]
        suffix = f" ({event.elapsed_s}s)" if event.elapsed_s else ""
        log_lines.append(f"{STATUS_ICONS[event.status]} **{event.agent}** {event.status}: {event.detail}{suffix}")
        shown += 1

    banner = DECISION_BANNERS.get(result.decision, result.decision)
    letter = result.response.letter if result.response else (result.error or "no response")
    audit = {
        "context_id": result.context_id,
        "extracted_claim": result.extracted.model_dump() if result.extracted else None,
        "validation": result.validation.model_dump() if result.validation else None,
        "reasoning_chain": result.response.reasoning_chain if result.response else [],
        "error": result.error,
    }
    yield render_log(), banner, letter, json.dumps(audit, indent=2)


with gr.Blocks(title="ClaimsPilot — A2A Multi-Agent Claims Processing") as demo:
    gr.Markdown(
        "# ✈️ ClaimsPilot\n"
        "Three independent agents — **Extractor → Validator (CrewAI + MCP) → Responder** — "
        "connected via the **A2A protocol**. Upload a claim and watch the handoffs."
    )
    with gr.Row():
        with gr.Column(scale=1):
            file_in = gr.File(label="Upload claim (PDF or TXT)", type="filepath")
            sample_in = gr.Dropdown(
                choices=list_samples(),
                label="…or pick a generated sample",
                value=None,
            )
            run_btn = gr.Button("Process claim", variant="primary")
            log_out = gr.Markdown("*Agent log will stream here*")
        with gr.Column(scale=1):
            banner_out = gr.Markdown()
            letter_out = gr.Textbox(label="Response letter", lines=12)
            audit_out = gr.Code(label="Full audit trail (JSON)", language="json")

    run_btn.click(process, inputs=[file_in, sample_in],
                  outputs=[log_out, banner_out, letter_out, audit_out])

if __name__ == "__main__":
    demo.launch()
