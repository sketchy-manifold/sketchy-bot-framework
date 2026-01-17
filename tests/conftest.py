# Read tests/knowledge.md in this directory for how to run tests.
import sys
from pathlib import Path

# Determine project root (one level up from tests/)
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# Add project root (for imports like 'import config')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Add src directory (for imports like 'import mymodule' from src/)
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Disable logging during tests
from config import LogConfig
LogConfig.ENABLED = False
