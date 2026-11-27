"""Entrypoint for `python -m app.py` — loads root `app.py` and runs `main()`."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _run() -> None:
    root_app = Path(__file__).resolve().parent.parent / "app.py"
    spec = importlib.util.spec_from_file_location("learnforge_root_app", root_app)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not locate {root_app}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


if __name__ == "__main__":
    _run()
