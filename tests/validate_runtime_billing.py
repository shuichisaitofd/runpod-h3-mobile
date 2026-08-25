from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "h3-mobile" / "web" / "index.html").read_text()
RUNTIME_JS = (ROOT / "h3-mobile" / "web" / "pod-runtime.js").read_text()
BILLING_JS = (ROOT / "h3-mobile" / "web" / "pod-billing.js").read_text()
EXTRA = (ROOT / "h3-mobile" / "extra_routes.py").read_text()
INIT = (ROOT / "h3-mobile" / "__init__.py").read_text()
RUN = (ROOT / "run.sh").read_text()

# Header and frontend assets must remain wired into the shipped UI.
assert 'id="runtime"' in INDEX
assert 'id="billing"' in INDEX
assert 'src="pod-runtime.js"' in INDEX
assert 'src="pod-billing.js"' in INDEX

# Runtime clock must come from the server-side PID1/container uptime endpoint.
assert "/h3-mobile/api/runtime" in INIT
assert "uptime_seconds" in INIT
assert "/h3-mobile/api/runtime" in RUNTIME_JS

# Billing endpoint must expose account balance/remaining time when the account key
# is configured, while retaining this Pod's own hourly cost as a fallback signal.
assert "/h3-mobile/api/pod-billing" in EXTRA
assert "RUNPOD_BILLING_API_KEY" in EXTRA
assert "estimated_hours_remaining" in EXTRA
assert "cost_per_hour" in EXTRA
assert "/h3-mobile/api/pod-billing" in BILLING_JS
assert "RUNPOD_BILLING_API_KEY not set" in BILLING_JS
assert "キー未設定" in BILLING_JS

# Fresh-Pod startup must explicitly support a RunPod Template/Secret injected key
# and loudly identify the missing-key state instead of silently degrading.
assert "RUNPOD_BILLING_API_KEY" in RUN
assert "BILLING_KEY_MISSING" in RUN
assert "RunPod Template/Secret" in RUN
assert "/workspace/.secrets/runpod_billing.env" in RUN

print("Runtime/Billing validation OK: header + endpoints + missing-key diagnostics + fresh-Pod env support")
