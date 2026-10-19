import sys
from pathlib import Path


def add_backend() -> Path:
    backend = Path(__file__).resolve().parent / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    return backend
