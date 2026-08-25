from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "h3-mobile" / "web" / "index.html").read_text()
RUNTIME_JS = (ROOT / "h3-mobile" / "web" / "pod-runtime.js").read_text()
BILLING_JS = (ROOT / "h3-mobile" / "web" / "pod-billing.js").read_text()
EXTRA = (ROOT / "h3-mobile" / "extra_routes.py").read_text()
INIT = (ROOT / "h3-mobile" / "__init__.py").read_text()

# Header and frontend assets must remain wired into the shipped UI.
assert 'id="runtime"' in INDEX
assert 'id="billing"' in INDEX
assert 'src="pod-runtime.js"' in INDEX
assert 'src="pod-billing.js"' in INDEX

# Runtime clock must come from server-side container uptime.
assert "/h3-mobile/api/runtime" in INIT
assert "uptime_seconds" in INIT
assert "/h3-mobile/api/runtime" in RUNTIME_JS

# Billing supports the legacy GET path plus a browser-key POST path. The browser
# keeps account keys in localStorage and sends them transiently as form data;
# the Pod must never need to persist the account key for this mode.
assert '@routes.get("/h3-mobile/api/pod-billing")' in EXTRA
assert '@routes.post("/h3-mobile/api/pod-billing")' in EXTRA
assert 'billing_api_key = (form.get("billing_api_key")' in EXTRA
assert 'query { myself { id clientBalance currentSpendPerHr } }' in EXTRA
assert "estimated_hours_remaining" in EXTRA
assert "cost_per_hour" in EXTRA

assert "h3RunPodBillingAccountsV1" in BILLING_JS
assert "h3RunPodBillingActiveAccountV1" in BILLING_JS
assert "h3RunPodBillingPodMapV1" in BILLING_JS
assert "localStorage" in BILLING_JS
assert "URLSearchParams" in BILLING_JS
assert "billing_api_key" in BILLING_JS
assert "保存して接続" in BILLING_JS
assert "再入力は不要" in BILLING_JS
assert "残り" in BILLING_JS

print("Runtime/Billing validation OK: uptime + browser-persisted multi-account balance/remaining-time flow")
