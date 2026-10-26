"""No API key and no completion request: compare system proxy and direct TLS."""
from urllib.request import build_opener, ProxyHandler
from urllib.error import HTTPError


def check(direct):
    # No prompt or Authorization header; only checks HTTP reachability.
    opener = build_opener(ProxyHandler({})) if direct else build_opener()
    try:
        with opener.open("https://api.deepseek.com/models", timeout=8) as response:
            return f"HTTP {response.status}: reachable"
    except HTTPError as exc:
        return f"HTTP {exc.code}: server responded (no key was sent)"
    except Exception as exc:
        return f"{type(exc).__name__}: connection failed"


if __name__ == "__main__":
    # Registry/proxy discovery may not obey socket timeouts; run separately.
    for label, direct in [("system_proxy", False), ("direct", True)]:
        print(f"Checking {label} (no tokens consumed)...", flush=True)
        # Explicit subprocess with bounded lifetime instead of waiting forever.
        import subprocess
        import sys
        from pathlib import Path
        script_dir = str(Path(__file__).resolve().parent)
        code = f"import sys; sys.path.insert(0, {script_dir!r}); from check_connection import check; print(check({direct!r}))"
        try:
            result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=12)
            print(label + ": " + (result.stdout.strip() or "diagnostic failed"), flush=True)
        except subprocess.TimeoutExpired:
            print(label + ": discovery_or_connection_timeout", flush=True)
