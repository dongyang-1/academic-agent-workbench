from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from .runtime import USER_AGENT


def download_open_pdfs(payload: dict[str, Any], output_dir: Path, limit: int | None = None,
                       timeout: int = 60) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = [record for record in payload.get("records", []) if record.get("open_access_pdf_url")]
    if limit is not None:
        candidates = candidates[:limit]
    manifest = []
    for record in candidates:
        url = record["open_access_pdf_url"]
        filename = re.sub(r"[^A-Za-z0-9._-]+", "-", record["record_id"]) + ".pdf"
        path = output_dir / filename
        headers = {"User-Agent": USER_AGENT, "Accept": "application/pdf"}
        if "api.core.ac.uk" in url:
            api_key = os.environ.get("CORE_API_KEY")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = response.read()
            if not content.startswith(b"%PDF"):
                raise ValueError("response is not a PDF")
            path.write_bytes(content)
            manifest.append({"record_id": record["record_id"], "status": "downloaded", "path": str(path), "url": url})
        except Exception as exc:
            manifest.append({"record_id": record["record_id"], "status": "failed", "path": None, "url": url, "error": str(exc)})
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Download only explicitly open-access PDFs from search output.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    manifest = download_open_pdfs(payload, args.output_dir, args.limit, args.timeout)
    manifest_path = args.output_dir / "download-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "items": len(manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
