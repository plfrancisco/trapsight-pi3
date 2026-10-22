"""Vercel entrypoint for the TrapSight API and same-origin frontend."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from src.main import app  # noqa: E402

app.frontend("/", directory=str(ROOT / "frontend" / "dist"), fallback="index.html")
