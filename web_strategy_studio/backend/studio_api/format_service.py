"""Format strategy source with Black (server-side)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


def format_python(source: str, timeout: float = 30.0) -> Dict[str, Any]:
    proc = None
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(source)
            tmp_path = f.name
        proc = subprocess.run(
            [sys.executable, "-m", "black", "-q", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out_path = Path(tmp_path)
        formatted = out_path.read_text(encoding="utf-8") if out_path.exists() else source
        ok = proc.returncode == 0
        return {
            "formatted_source": formatted,
            "ok": ok,
            "message": None if ok else (proc.stderr or "black failed"),
        }
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"formatted_source": source, "ok": False, "message": str(e)}
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
