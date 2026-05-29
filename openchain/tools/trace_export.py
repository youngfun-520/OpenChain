"""Trace export utilities."""
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openchain.session import SessionManager


async def write_trace_to_file(sm: "SessionManager", session_id: str, output_path: str) -> dict:
    """Export session trace and write to a JSON file."""
    trace = await sm.export_trace(session_id)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(trace, f, indent=2, default=str)
    return {"status": "success", "path": str(path), "size_bytes": path.stat().st_size}