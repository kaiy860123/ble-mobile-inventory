import argparse
import json
import os
from pathlib import Path
from aiohttp import web
from .config import load_config
from .server import create_app


def main():
    parser = argparse.ArgumentParser(description="BLE mobile inventory")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--config", default="config/site.example.json")
    serve.add_argument("--root", default=".")
    serve.add_argument("--mode", choices=["demo", "ble", "external"], default="demo")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if args.command == "serve":
        config = load_config(args.config)
        if args.mode == "external" and not os.environ.get("BLE_INGEST_TOKEN"):
            parser.error("external mode requires BLE_INGEST_TOKEN in the environment")
        app = create_app(config, Path(args.root), args.mode, os.environ.get("BLE_INGEST_TOKEN"), config_path=args.config)
        print(f"Input mode: {args.mode}; demo is synthetic data, not Gazebo or hardware validation.")
        web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
