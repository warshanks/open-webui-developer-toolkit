
# Ensure the ``src/`` directory is on ``sys.path`` for test imports.
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
