import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
ENGINES = ROOT.parent / "engines"
load_dotenv(ROOT / ".env")  # local runs; in Docker the env comes from --env-file

CF_ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"]
CF_QUEUE_ID = os.environ["CF_QUEUE_ID"]
CF_API_TOKEN = os.environ["CF_API_TOKEN"]
API_URL = os.environ["API_URL"].rstrip("/")
INTERNAL_KEY = os.environ["INTERNAL_KEY"]

# In Docker both engines share the image's Python; locally point these at each engine's venv.
REELS_PYTHON = os.getenv("REELS_PYTHON", sys.executable)
MOTION_PYTHON = os.getenv("MOTION_PYTHON", sys.executable)
RENDER_WORKERS = os.getenv("RENDER_WORKERS", "2")  # browser slots per render; 4 GB VM → 2
MOTION_BUDGET_USD = os.getenv("MOTION_BUDGET_USD", "1.00")  # hard cap on model spend per motion film

POLL_SECONDS = 5
IDLE_EXIT_MINUTES = float(os.getenv("IDLE_EXIT_MINUTES", "0"))  # > 0: exit when the queue stays empty this long (the VM then powers off)
LEASE_MS = 60 * 60 * 1000  # a job must finish within an hour or it goes back on the queue
