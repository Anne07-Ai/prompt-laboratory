"""Run the Prompt Laboratory API and dashboard in one Hugging Face container."""

from __future__ import annotations

import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

API_URL = "http://127.0.0.1:8000"


def configure_environment() -> None:
    """Apply safe, ephemeral defaults for the public demonstration."""
    data_dir = Path(os.getenv("PROMPT_LAB_HF_DATA_DIR", "/tmp/prompt-laboratory"))
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{data_dir / 'demo.db'}")
    os.environ.setdefault("PROMPT_LAB_PROMPTS_DIR", "/app/prompts")
    os.environ.setdefault("PROMPT_LAB_API_URL", API_URL)
    os.environ["PROMPT_LAB_DEMO_MODE"] = "true"
    if len(os.getenv("PROMPT_LAB_AUTH_SECRET", "")) < 32:
        os.environ["PROMPT_LAB_AUTH_SECRET"] = secrets.token_urlsafe(48)
    if len(os.getenv("PROMPT_LAB_CREDENTIAL_KEY", "")) < 32:
        os.environ["PROMPT_LAB_CREDENTIAL_KEY"] = secrets.token_urlsafe(48)
    for provider_key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(provider_key, None)


def wait_for_api(process: subprocess.Popen[bytes], timeout_seconds: int = 45) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Prompt Laboratory API exited with code {process.returncode}")
        try:
            with urllib.request.urlopen(f"{API_URL}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Prompt Laboratory API did not become ready")


def terminate(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    configure_environment()
    api: subprocess.Popen[bytes] | None = None
    dashboard: subprocess.Popen[bytes] | None = None
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    try:
        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "prompt_laboratory.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ]
        )
        wait_for_api(api)
        dashboard = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "dashboard/app.py",
                "--server.address=0.0.0.0",
                "--server.port=7860",
                "--server.headless=true",
                "--browser.gatherUsageStats=false",
            ]
        )
        while not stopping:
            if api.poll() is not None:
                raise RuntimeError(f"Prompt Laboratory API exited with code {api.returncode}")
            if dashboard.poll() is not None:
                return int(dashboard.returncode or 0)
            time.sleep(0.5)
        return 0
    finally:
        terminate(dashboard)
        terminate(api)


if __name__ == "__main__":
    raise SystemExit(main())
