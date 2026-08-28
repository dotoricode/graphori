"""Start the local Graphori HUD: python scripts/dashboard_server.py --root ."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from graphori_core.dashboard import create_server  # noqa: E402

parser = argparse.ArgumentParser(description="Graphori local dashboard")
parser.add_argument("--root", default=".", help="workspace containing .graphori/runs")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8765)
args = parser.parse_args()
server = create_server(args.root, host=args.host, port=args.port, static_dir=ROOT / "docs" / "dashboard")
print(f"Graphori HUD: http://{args.host}:{args.port}/")
try: server.serve_forever()
except KeyboardInterrupt: pass
finally: server.server_close()
