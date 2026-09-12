// Real-browser integration test for the LoRA upload progress UI.
//
// Starts a local HTTP server that serves the real h3-mobile/web files and a
// deliberately SLOW multipart /loras/upload endpoint, drives the real page in
// headless Chromium (Playwright), and asserts the DOM actually shows
//   待機中 → アップロード中 xx% (updating) → サーバー検証中 → ✓ 導入済み
// It also proves a failing /loras/files mid-upload never wipes the list.
//
// This is NOT a substitute for a RunPod real-device test — RunPod proxy
// buffering behaviour is not reproduced here.
//
// Env:
//   PLAYWRIGHT_MODULE      override the module to import (default: try
//                          'playwright' then 'playwright-core')
//   PW_EXECUTABLE_PATH     explicit Chromium/headless-shell binary
//   ALLOW_SKIP=1           exit 0 with "SKIPPED" if no browser can launch
import http from 'node:http';
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const WEB = join(ROOT, 'h3-mobile', 'web');

function loadPlaywright() {
  const names = process.env.PLAYWRIGHT_MODULE
    ? [process.env.PLAYWRIGHT_MODULE]
    : ['playwright', 'playwright-core'];
  const extra = [
    process.env.PLAYWRIGHT_CORE_PATH,
    '/tmp/pw-test/node_modules/playwright-core',
  ].filter(Boolean);
  for (const n of [...names, ...extra]) {
    try { return require(n); } catch { /* try next */ }
  }
  return null;
}

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' };

// ---- test-controlled server behaviour -----------------------------------
const cfg = { filesDelayMs: 0, filesFail: false, uploadChunkDelayMs: 20, verifyDelayMs: 700 };
const installed = new Set();          // filenames that "exist on the Pod"
const uploadLog = [];                 // {filename, bytes, ts}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { 'content-type': 'application/json', 'access-control-allow-origin': '*' });
  res.end(body);
}

async function handleUpload(req, res, url) {
  const filename = url.searchParams.get('filename') || 'unknown.safetensors';
  const expected = url.searchParams.get('expected_sha256') || '';
  let bytes = 0;
  try {
    for await (const chunk of req) {
      bytes += chunk.length;
      if (cfg.uploadChunkDelayMs) await sleep(cfg.uploadChunkDelayMs); // throttle -> real progress events
    }
  } catch (e) {
    res.writeHead(400); res.end('upload aborted'); return;
  }
  // request body fully received: now "verify" (hash) for a while
  await sleep(cfg.verifyDelayMs);
  const sha = 'a'.repeat(64);
  if (expected && expected !== sha) { res.writeHead(409); res.end(`uploaded file SHA256 mismatch: expected ${expected}, got ${sha}`); return; }
  installed.add(filename);
  uploadLog.push({ filename, bytes, ts: Date.now() });
  sendJson(res, 200, { ok: true, filename, size: bytes, sha256: sha });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const p = url.pathname;
  try {
    if (p === '/__test/config' && req.method === 'POST') {
      let raw = ''; for await (const c of req) raw += c;
      Object.assign(cfg, JSON.parse(raw || '{}'));
      return sendJson(res, 200, { ok: true, cfg });
    }
    if (p === '/__test/state') return sendJson(res, 200, { installed: [...installed], uploadLog, cfg });

    if (p === '/h3-mobile/api/loras/upload' && req.method === 'POST') return handleUpload(req, res, url);
    if (p === '/h3-mobile/api/loras/files') {
      if (cfg.filesDelayMs) await sleep(cfg.filesDelayMs);
      if (cfg.filesFail) { res.writeHead(500); res.end('files unavailable'); return; }
      return sendJson(res, 200, { files: [...installed].map((f) => ({ filename: f, status: 'installed', size: 1024, uploading: false })) });
    }
    if (p === '/h3-mobile/api/loras/delete' && req.method === 'POST') { installed.clear(); return sendJson(res, 200, { ok: true }); }

    // minimal stubs so app.js boot does not throw
    if (p === '/h3-mobile/health') return sendJson(res, 200, { ok: true, service: 'h3-mobile' });
    if (p === '/system_stats') return sendJson(res, 200, { system: {}, devices: [] });
    if (p === '/h3-mobile/api/runtime') return sendJson(res, 200, { ok: true, uptime_seconds: 0 });
    if (p === '/h3-mobile/api/models') return sendJson(res, 200, { models: {}, sets: {} });
    if (p.startsWith('/h3-mobile/api/workflow/')) return sendJson(res, 200, {});
    if (p === '/history') return sendJson(res, 200, {});
    if (p === '/queue') return sendJson(res, 200, { queue_running: [], queue_pending: [] });
    if (p === '/h3-mobile/api/pod-billing') return sendJson(res, 200, { ok: false });
    if (p === '/h3-mobile/api/pod-runtime') return sendJson(res, 200, { ok: false });
    if (p === '/h3-mobile/api/input-images') return sendJson(res, 200, { images: [] });
    if (p === '/prompt' && req.method === 'POST') return sendJson(res, 200, { prompt_id: 'x' });

    // static: /h3-mobile/ and /h3-mobile/<file>
    if (p === '/h3-mobile/' || p === '/h3-mobile') {
      res.writeHead(200, { 'content-type': 'text/html' });
      res.end(readFileSync(join(WEB, 'index.html')));
      return;
    }
    if (p.startsWith('/h3-mobile/')) {
      const name = p.slice('/h3-mobile/'.length);
      if (name && !name.includes('..')) {
        try {
          const buf = readFileSync(join(WEB, name));
          res.writeHead(200, { 'content-type': MIME[extname(name)] || 'application/octet-stream' });
          res.end(buf);
          return;
        } catch { /* fall through to 404 */ }
      }
    }
    res.writeHead(404); res.end('not found');
  } catch (e) {
    res.writeHead(500); res.end(String(e && e.stack || e));
  }
});

function fail(msg) { console.error('FAIL: ' + msg); process.exitCode = 1; throw new Error(msg); }
function ok(msg) { console.log('  ok - ' + msg); }

async function setConfig(base, patch) {
  const r = await fetch(base + '/__test/config', { method: 'POST', body: JSON.stringify(patch) });
  if (!r.ok) throw new Error('config failed');
}

// Record status/progress of a card (by visible name) at ~80ms cadence until
// it reads 導入済み or the timeout elapses.
async function recordCard(page, name, timeoutMs) {
  return page.evaluate(async ({ name, timeoutMs }) => {
    const samples = [];
    const started = Date.now();
    const pick = () => [...document.querySelectorAll('#h3LoraManager .h3-lora-item')]
      .find((el) => el.querySelector('.h3-lora-name')?.textContent === name);
    while (Date.now() - started < timeoutMs) {
      const row = pick();
      const itemCount = document.querySelectorAll('#h3LoraManager .h3-lora-item').length;
      const status = row?.querySelector('.h3-lora-status')?.textContent?.trim() || null;
      const progressEl = !!row?.querySelector('.h3-lora-progress');
      const barW = row?.querySelector('.h3-lora-progress > span')?.style.width || null;
      const info = row?.querySelector('.h3-lora-inline-progress')?.textContent?.trim() || null;
      samples.push({ t: Date.now() - started, itemCount, status, progressEl, barW, info });
      if (status && status.includes('導入済み')) break;
      await new Promise((r) => setTimeout(r, 80));
    }
    return samples;
  }, { name, timeoutMs });
}

async function main() {
  const pw = loadPlaywright();
  if (!pw) {
    if (process.env.ALLOW_SKIP === '1') { console.log('SKIPPED: playwright module not available'); return; }
    fail('playwright module not available (npm i playwright-core)');
  }
  const launchOpts = { headless: true };
  if (process.env.PW_EXECUTABLE_PATH) launchOpts.executablePath = process.env.PW_EXECUTABLE_PATH;

  let browser;
  try {
    browser = await pw.chromium.launch(launchOpts);
  } catch (e) {
    if (process.env.ALLOW_SKIP === '1') { console.log('SKIPPED: chromium launch failed: ' + String(e).split('\n')[0]); return; }
    throw e;
  }

  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;

  // ~5 MB dummy files (real multipart bodies, no real safetensors bytes)
  const dir = mkdtempSync(join(tmpdir(), 'lora-upload-'));
  const mk = (fn) => { const path = join(dir, fn); writeFileSync(path, Buffer.alloc(5 * 1024 * 1024, 7)); return path; };

  const page = await browser.newPage();
  page.on('pageerror', (e) => console.log('  [pageerror] ' + e.message));

  try {
    // -------- Scenario 1: determinate progress is actually visible ---------
    await setConfig(base, { filesFail: false, filesDelayMs: 0, uploadChunkDelayMs: 22, verifyDelayMs: 800 });
    await page.goto(base + '/h3-mobile/', { waitUntil: 'domcontentloaded' });
    await page.click('.nav[data-target="lora"]');
    await page.waitForSelector('#h3LoraManager .h3-lora-item', { timeout: 10000 });

    const nameA = 'Panties v1'; // catalog: Panties_v1.safetensors
    await page.setInputFiles('#loraNewFiles', mk('Panties_v1.safetensors'));
    const s1 = await recordCard(page, nameA, 20000);

    if (!s1.length) fail('scenario1: no samples');
    const first = s1[0];
    if (!first.status || first.status.includes('未導入')) fail(`scenario1: first status was "${first.status}" (expected 待機中/アップロード中/検証 synchronously)`);
    ok(`scenario1: status is "${first.status}" immediately (synchronous paint, not 未導入)`);

    if (!s1.some((x) => x.progressEl)) fail('scenario1: progress element never appeared');
    ok('scenario1: progress bar element present during upload');

    const infos = [...new Set(s1.map((x) => x.info).filter(Boolean))];
    const bars = [...new Set(s1.map((x) => x.barW).filter(Boolean))];
    if (infos.length < 2 && bars.length < 2) fail(`scenario1: progress never updated (infos=${infos.length}, bars=${bars.length})`);
    ok(`scenario1: progress updated over time (${infos.length} distinct info lines, ${bars.length} distinct bar widths)`);

    const sawUploading = s1.some((x) => x.status && x.status.includes('アップロード中'));
    if (!sawUploading) fail('scenario1: "アップロード中" never shown');
    ok('scenario1: "アップロード中" shown');

    const sawVerify = s1.some((x) => x.status && (x.status.includes('検証') || x.status.includes('verif')));
    if (!sawVerify) fail('scenario1: "検証中" never shown');
    ok('scenario1: "サーバー検証中" shown after body sent');

    const last = s1[s1.length - 1];
    if (!last.status || !last.status.includes('導入済み')) fail(`scenario1: final status "${last.status}" (expected 導入済み)`);
    ok('scenario1: ends at "✓ 導入済み"');

    if (s1.some((x) => x.itemCount === 0)) fail('scenario1: manager list was emptied at some point');
    ok('scenario1: manager list never emptied');

    // -------- Scenario 2: /loras/files failing mid-upload must not wipe UI --
    await setConfig(base, { filesFail: true, uploadChunkDelayMs: 22, verifyDelayMs: 1500 });
    const nameB = 'BJ v3';
    await page.setInputFiles('#loraNewFiles', mk('BJ_v3.safetensors'));
    // sample while files endpoint is 500ing
    const midSamples = await recordCard(page, nameB, 3500);
    if (midSamples.some((x) => x.itemCount === 0)) fail('scenario2: list emptied while /loras/files failing (regression)');
    if (!midSamples.some((x) => x.status && (x.status.includes('アップロード中') || x.status.includes('検証')))) {
      fail('scenario2: uploading card lost its status while /loras/files failing');
    }
    ok('scenario2: list + progress survive a failing /loras/files');
    // recover
    await setConfig(base, { filesFail: false });
    const s2 = await recordCard(page, nameB, 15000);
    if (!s2.length || !s2[s2.length - 1].status?.includes('導入済み')) fail('scenario2: did not reach 導入済み after recovery');
    ok('scenario2: reaches "✓ 導入済み" after /loras/files recovers');

    // -------- Scenario 3: multi-file selection shows 待機中 for pending -----
    await setConfig(base, { filesFail: false, uploadChunkDelayMs: 30, verifyDelayMs: 400 });
    await page.setInputFiles('#loraNewFiles', [mk('Nipple_v2.safetensors'), mk('Squirt_HM_v1.safetensors')]);
    // give the first upload a moment to start
    await page.waitForTimeout(400);
    const combo = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('#h3LoraManager .h3-lora-item')];
      const st = (n) => rows.find((r) => r.querySelector('.h3-lora-name')?.textContent === n)?.querySelector('.h3-lora-status')?.textContent?.trim();
      return { a: st('Nipple v2'), b: st('Squirt HM v1') };
    });
    const anyUploading = [combo.a, combo.b].some((s) => s && s.includes('アップロード中'));
    const anyWaiting = [combo.a, combo.b].some((s) => s && s.includes('待機中'));
    if (!anyUploading || !anyWaiting) fail(`scenario3: expected one アップロード中 + one 待機中, got ${JSON.stringify(combo)}`);
    ok('scenario3: pending file shows 待機中 while the first uploads');
    await recordCard(page, 'Squirt HM v1', 15000);

    console.log('\nreal-browser LoRA upload progress: ALL SCENARIOS PASSED');
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
