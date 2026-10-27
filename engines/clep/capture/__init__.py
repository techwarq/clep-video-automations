import sys
from pathlib import Path

CAPTURE_DIR = Path(__file__).resolve().parent
if str(CAPTURE_DIR) not in sys.path:
    sys.path.insert(0, str(CAPTURE_DIR))
