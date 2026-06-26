"""Makes src/ importable from the test files without installing the project
as a package -- every pipeline module uses plain `from config import ...`
style imports, so tests need src/ on sys.path the same way running a script
from inside src/ would put it there automatically.
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))
