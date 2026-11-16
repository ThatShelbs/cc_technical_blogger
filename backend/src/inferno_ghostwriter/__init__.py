"""Inferno Ghostwriter: write technical blog posts in your own voice."""

__version__ = "0.1.0"


def _open_when_ready(url: str, timeout: float = 60.0) -> None:
    """Open the browser once the server answers its health check."""
    import time
    import urllib.request
    import webbrowser

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


def _offer_demo(settings, *, interactive: bool) -> bool:  # type: ignore[no-untyped-def]
    """On a bare first launch (no data, no Claude connection) offer the demo instead of an app that cannot do anything yet."""
    from inferno_ghostwriter.doctor import claude_auth, should_offer_demo

    if not should_offer_demo(settings, claude_auth(settings), interactive=interactive):
        return False
    print("\n  No Claude connection found yet.")
    print("  Demo mode lets you look around now: canned AI responses, an example post, no keys, no cost.")
    answer = input("  Start in demo mode? [Y/n] ").strip().lower()
    return answer in ("", "y", "yes")


def main() -> None:
    """Console entry point: ``uv run inferno-ghostwriter`` starts the local web app."""
    import argparse
    import logging
    import os
    import sys
    import threading

    import uvicorn

    from inferno_ghostwriter.config import REPO_ROOT, get_settings

    settings = get_settings()
    parser = argparse.ArgumentParser(prog="inferno-ghostwriter", description="Run the Inferno Ghostwriter web app.")
    parser.add_argument(
        "command", nargs="?", choices=["doctor"], help="doctor: check this machine and explain how to fix anything missing."
    )
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--open", action="store_true", help="Open the app in your browser once it starts.")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (development).")
    parser.add_argument("--demo", action="store_true", help="Demo mode: canned AI responses, no API keys, separate data folder.")
    args = parser.parse_args()

    if args.command == "doctor":
        from inferno_ghostwriter.doctor import run_doctor

        raise SystemExit(run_doctor(settings))

    if not args.demo and not args.reload and _offer_demo(settings, interactive=sys.stdin.isatty() and sys.stdout.isatty()):
        args.demo = True

    if args.demo:
        # The app factory reads settings from the environment, so pass demo mode that way.
        os.environ["INFERNO_GHOSTWRITER_DEMO"] = "1"
        os.environ.setdefault("INFERNO_GHOSTWRITER_DATA_DIR", str(settings.data_dir / "demo"))
        get_settings.cache_clear()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    url = f"http://{args.host}:{args.port}"
    print(f"\n  Inferno Ghostwriter is starting at {url}  (press Ctrl+C to stop)\n", flush=True)
    if args.open and not os.environ.get("INFERNO_GHOSTWRITER_NO_BROWSER"):
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(
        "inferno_ghostwriter.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(REPO_ROOT / "backend" / "src")] if args.reload else None,
    )
