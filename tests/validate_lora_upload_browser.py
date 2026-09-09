"""Wrapper: run the real-browser LoRA upload progress integration test.

Runs tests/integration_lora_upload_browser.mjs in headless Chromium via
Playwright with a real slow multipart upload endpoint.

- If a Playwright module and a Chromium binary are found, the integration test
  runs and its exit code is propagated.
- Otherwise this SKIPS (exit 0) unless REQUIRE_BROWSER_TEST=1, in which case it
  fails. CI sets REQUIRE_BROWSER_TEST=1 after installing the browser.

A FakeXHR-only unit test is NOT a substitute for this and must never be
reported as "real upload progress verified".
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MJS = ROOT / "tests" / "integration_lora_upload_browser.mjs"

REQUIRE = os.environ.get("REQUIRE_BROWSER_TEST") == "1"


def find_playwright_module():
    if os.environ.get("PLAYWRIGHT_MODULE"):
        return os.environ["PLAYWRIGHT_MODULE"]
    candidates = [
        ROOT / "node_modules" / "playwright",
        ROOT / "node_modules" / "playwright-core",
        ROOT / "tests" / "node_modules" / "playwright",
        ROOT / "tests" / "node_modules" / "playwright-core",
        Path("/tmp/pw-test/node_modules/playwright-core"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # global resolution
    try:
        subprocess.run(["node", "-e", "require('playwright-core')"], check=True,
                       capture_output=True)
        return "playwright-core"
    except Exception:
        try:
            subprocess.run(["node", "-e", "require('playwright')"], check=True,
                           capture_output=True)
            return "playwright"
        except Exception:
            return None


def find_chromium():
    if os.environ.get("PW_EXECUTABLE_PATH"):
        return os.environ["PW_EXECUTABLE_PATH"]
    roots = [
        Path.home() / "Library" / "Caches" / "ms-playwright",
        Path.home() / ".cache" / "ms-playwright",
    ]
    names = ("chrome-headless-shell", "headless_shell", "chrome", "Chromium",
             "Google Chrome for Testing")
    for root in roots:
        if not root.is_dir():
            continue
        for name in names:
            hits = sorted(root.glob(f"**/{name}"))
            for h in hits:
                if h.is_file() and os.access(h, os.X_OK):
                    return str(h)
    return None


def main():
    if not shutil.which("node"):
        msg = "node not available"
        if REQUIRE:
            print(f"FAIL: {msg}")
            return 1
        print(f"SKIPPED: {msg}")
        return 0

    module = find_playwright_module()
    if not module:
        msg = "no Playwright module (npm i playwright-core)"
        if REQUIRE:
            print(f"FAIL: {msg}")
            return 1
        print(f"SKIPPED: {msg}")
        return 0

    env = dict(os.environ)
    env["PLAYWRIGHT_MODULE"] = module
    exe = find_chromium()
    if exe:
        env["PW_EXECUTABLE_PATH"] = exe
    elif not REQUIRE:
        env["ALLOW_SKIP"] = "1"

    print(f"running {MJS.name} (module={module}, chromium={'auto' if not exe else exe})")
    result = subprocess.run(["node", str(MJS)], env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
