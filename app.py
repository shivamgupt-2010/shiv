"""
ShivAI Unified 24/7 Cloud Application.
Runs on 16 GB CPU with unlimited usage (no GPU quotas or timeouts).
Serves both the Gradio Web Chat UI and the complete FastAPI REST API.
"""
import sys
import os
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gradio as gr
from database.session import init_db, async_session_factory
from core.orchestration.orchestrator import ShivAIOrchestrator
from apps.api.main import app as fastapi_app


async def shivai_chat_response(message: str, history):
    """Native asynchronous streaming generator for Gradio chat."""
    try:
        await init_db()
        async with async_session_factory() as session:
            orchestrator = ShivAIOrchestrator(session)
            partial = ""
            stream = orchestrator.process_chat_stream(
                user_message=message,
                user_id="web-user",
                request_id=f"hf-{int(time.time())}",
            )
            async for chunk in stream:
                if chunk.delta:
                    partial += chunk.delta
                    yield partial
            await session.commit()
    except Exception as e:
        yield f"ShivAI encountered an issue: {str(e)}"


# Create Gradio Web UI
with gr.Blocks(title="ShivAI - Independent AI Companion") as demo:
    gr.Markdown("# ⚡ ShivAI — Independent AI Companion")
    gr.Markdown(
        "Welcome to **ShivAI**. Powered by an independent multi-model architecture "
        "with dynamic routing across **Google Gemini**, **Groq**, and **Llama 3**."
    )
    gr.ChatInterface(
        fn=shivai_chat_response,
    )

# Mount Gradio onto the existing FastAPI application
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
