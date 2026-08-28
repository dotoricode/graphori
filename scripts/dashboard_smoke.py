"""Run a finite dashboard HTTP smoke test without external dependencies."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from graphori_core.dashboard import create_server


def main() -> int:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        static = root / "static"
        static.mkdir()
        (static / "index.html").write_text("<html>Graphori</html>", encoding="utf-8")
        server = create_server(root, static_dir=static)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_address[1]}/", timeout=5) as response:
                body = response.read().decode("utf-8")
            if "Graphori" not in body:
                raise RuntimeError("dashboard response did not contain expected marker")
            print(json.dumps({"status": "pass", "transport": "http", "finite": True}))
        finally:
            server.shutdown()
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
