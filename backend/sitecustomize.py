from __future__ import annotations

import site
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
VENDOR_DIR = BASE_DIR / "_vendor"


def _add_path(path: Path) -> None:
    candidate = str(path)
    if path.exists() and candidate not in sys.path:
        sys.path.insert(0, candidate)


_add_path(VENDOR_DIR)

try:
    user_site = Path(site.getusersitepackages())
except Exception:
    user_site = None

if user_site:
    _add_path(user_site)
