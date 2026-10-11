"""Optional SAM3 weight download helper."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def ensure_weights(
    weights_path: str | Path,
    repo_id: str = "1038lab/sam3",
    filename: str = "sam3.pt",
    token: str | None = None,
) -> Path:
    path = Path(weights_path)
    if path.exists():
        return path
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("Install huggingface_hub to download SAM3 weights.") from exc
    token = token or os.environ.get("HF_TOKEN")
    downloaded = hf_hub_download(
        repo_id=repo_id, filename=filename, token=token, local_dir=str(path.parent or Path("."))
    )
    if Path(downloaded).resolve() != path.resolve():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(downloaded, path)
    return path
