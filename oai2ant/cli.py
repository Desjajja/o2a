from __future__ import annotations

import argparse
import atexit
import contextlib
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

import httpx
import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROXY_HOST = "0.0.0.0"
DEFAULT_PROXY_PORT = 8082
DEFAULT_UI_HOST = "127.0.0.1"
DEFAULT_UI_PORT = 5173
DEFAULT_PROXY_CHECK_HOST = "127.0.0.1"


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="o2a",
        description="Control the oai2ant proxy service or admin UI",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_PROXY_HOST,
        help=f"Proxy bind host (default: {DEFAULT_PROXY_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PROXY_PORT,
        help=f"Proxy bind port (default: {DEFAULT_PROXY_PORT})",
    )
    parser.add_argument(
        "--reload",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Enable FastAPI autoreload (default: on)",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Uvicorn log level",
    )
    parser.add_argument(
        "--ui",
        default=False,
        action="store_true",
        help="Start only the React admin UI (requires proxy to be running)",
    )
    parser.add_argument(
        "--ui-host",
        default=DEFAULT_UI_HOST,
        help=f"Admin UI host when --ui is used (default: {DEFAULT_UI_HOST})",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=DEFAULT_UI_PORT,
        help=f"Admin UI port when --ui is used (default: {DEFAULT_UI_PORT})",
    )
    parser.add_argument(
        "--open-browser",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Open the admin UI in the browser when --ui is used (default: on)",
    )
    parser.add_argument(
        "--proxy-host",
        default=DEFAULT_PROXY_CHECK_HOST,
        help=f"Proxy host for health checks when --ui is used (default: {DEFAULT_PROXY_CHECK_HOST})",
    )
    parser.add_argument(
        "--proxy-port",
        type=int,
        default=DEFAULT_PROXY_PORT,
        help=f"Proxy port for health checks when --ui is used (default: {DEFAULT_PROXY_PORT})",
    )
    return parser.parse_args(argv)


def _start_ui(host: str, port: int) -> subprocess.Popen[str]:
    npm_command = [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        host,
        "--port",
        str(port),
    ]
    env = os.environ.copy()
    env.setdefault("BROWSER", "none")
    try:
        process = subprocess.Popen(
            npm_command,
            cwd=str(PROJECT_ROOT / "ui"),
            env=env,
            stdin=None,
        )
    except FileNotFoundError as exc:  # pragma: no cover - depends on local toolchain
        raise RuntimeError("npm command not found; install Node.js to run the admin UI") from exc
    return process


def _open_browser(host: str, port: int) -> None:
    url = f"http://{host}:{port}"

    def _delayed_open() -> None:
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=_delayed_open, daemon=True).start()


def _ensure_proxy_running(
    url: str, attempts: int = 5, delay: float = 0.6, timeout: float = 1.0
) -> None:
    for _ in range(attempts):
        try:
            response = httpx.get(url, timeout=timeout)
        except httpx.HTTPError:
            response = None
        if response and response.status_code == 200:
            return
        time.sleep(delay)
    raise RuntimeError(f"Proxy not reachable at {url}")


def _run_proxy(host: str, port: int, reload: bool, log_level: str) -> None:
    config = uvicorn.Config(
        "proxy.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        reload_dirs=[
            str(PROJECT_ROOT / "proxy"),
            str(PROJECT_ROOT / "config"),
        ],
    )
    server = uvicorn.Server(config)
    server.run()


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    if args.ui:
        proxy_url = f"http://{args.proxy_host}:{args.proxy_port}/health"
        try:
            _ensure_proxy_running(proxy_url)
        except RuntimeError as exc:
            print(f"[o2a] {exc}", file=sys.stderr)
            return 1

        print(f"[o2a] Proxy detected at {proxy_url}")
        print(f"[o2a] Starting admin UI at http://{args.ui_host}:{args.ui_port}")
        ui_process = _start_ui(args.ui_host, args.ui_port)

        def _cleanup() -> None:
            if ui_process.poll() is None:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    ui_process.terminate()
                    ui_process.wait(timeout=5)
            if ui_process.poll() is None:
                ui_process.kill()

        atexit.register(_cleanup)

        if args.open_browser:
            with contextlib.suppress(Exception):
                _open_browser(args.ui_host, args.ui_port)

        try:
            ui_process.wait()
        except KeyboardInterrupt:  # pragma: no cover - interactive session
            pass
        finally:
            if ui_process.poll() is None:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    ui_process.terminate()
                    ui_process.wait(timeout=5)
                if ui_process.poll() is None:
                    ui_process.kill()
        return ui_process.returncode or 0

    print(f"[o2a] Starting proxy at http://{args.host}:{args.port}")
    try:
        _run_proxy(args.host, args.port, args.reload, args.log_level)
    except KeyboardInterrupt:  # pragma: no cover - interactive session
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
