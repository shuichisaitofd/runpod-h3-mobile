# H3 Mobile LoRA Test Status

- State: offline tests + local real-browser upload-progress test VERIFIED /
  RunPod real-device test: NOT STARTED
- Branch: `codex/h3-lora-mobile-test`
- Base SHA: `04f1d4f2827f055a79ac88ccc0c9f35a81996ab2`

## LoRA management is file-only

User LoRAs are added by **file upload only**. There is no URL / Civitai path
anywhere:

- Frontend: no URL field, no "URLから追加", no "URLから一括再導入", no Civitai
  API-key UI, no `resolveUrl` / `downloadItem` / `bulkDownloadUrls` helpers, no
  `sourceType` / `installMethod` record fields.
- Backend (`h3-mobile/lora_routes.py`): only `GET /h3-mobile/api/loras/files`,
  `POST /h3-mobile/api/loras/upload`, `POST /h3-mobile/api/loras/delete`. The
  `resolve` / `download` endpoints, the `aiohttp` client downloader, redirect
  handling and request headers are removed.

The H3 body / Qwen / VAE / Turbo LoRA **model auto-download** in
`h3-mobile/__init__.py` is a separate feature and is unchanged.

### Adding a LoRA

`.safetensors` files, multi-select. Per file:

| Case | Result |
| --- | --- |
| filename matches an existing registration | treated as that LoRA |
| filename matches the default catalog | registered as that default |
| unknown `.safetensors` | auto-registered as a **custom** LoRA (name from filename, `defaultStrength` 1.0, OFF in every context) |

Re-uploading the same filename never creates a duplicate registration. In a
multi-file upload, one file failing does not stop the others.

## Upload status shown on the card

`未導入 → 待機中 → アップロード中 xx% → サーバー検証中 → ✓ 導入済み`, or `✕ 導入失敗`.

- The manager list is painted **synchronously** from three inputs —
  registrations (`localStorage`), the last known Pod file list (cached), and
  this browser's in-flight uploads — by `paintManager()`, with **no network
  call**. So the "待機中 / アップロード中 0%" row and its progress bar are in the
  DOM the instant a file is chosen, *before* `xhr.send()` runs. It no longer
  depends on a `/loras/files` fetch resolving first.
- Progress uses `XMLHttpRequest.upload.onloadstart` + `.upload.onprogress`
  (bytes + percent + bar); `.upload.onload` moves to サーバー検証中.
- If the transfer is **not length-computable** (a proxy stripped
  `Content-Length`), the card shows an animated indeterminate bar + "送信済み X
  MB" instead of a percentage — never blank.
- A 1-second heartbeat updates the "サーバー検証中 (Ns)" / "アップロード中 (Ns)"
  text so a slow phase never looks frozen.
- A slow or failing `/loras/files` (very possible while a large multipart POST
  saturates the RunPod proxy) **never wipes the list** — `renderManager()`
  keeps the last known state, shows a small "Pod状態を更新できません" note, and a
  background retry heals it. The old "LoRA状態の取得に失敗" full-list-replace is
  gone.
- On upload success the server has already `os.replace`-d the file, so the card
  is marked `✓ 導入済み` optimistically even if the follow-up `/loras/files`
  refresh is slow/failing.
- `✓ 導入済み` is otherwise driven **only** by a real non-empty `*.safetensors`
  on the Pod. `localStorage` alone never marks a LoRA installed. A
  `*.upload.part` or a 0-byte file is never "installed".
- On failure the card keeps an error state (reason + `詳細` raw text + `再試行`)
  until the next action — no console/terminal needed to see why.

### Why the first attempt was insufficient

The first pass wired `XMLHttpRequest.upload.onprogress` but `runUpload()` called
the async `renderManager()` (which fetches `/loras/files`) **without awaiting**
before `xhr.send()`. The progress-bar markup was therefore not in the DOM when
the first progress events fired, so the in-place updater silently no-opped; and
a failing `/loras/files` replaced the whole list with an error notice, erasing
any progress. On RunPod, where that GET competes with the upload through the
proxy, the net effect was **no visible progress at all**. The
`validate_lora_file_only.py` FakeXHR test only fired synthetic events and never
exercised real DOM timing, so it missed this. That test is no longer treated as
"real progress verified".

## SHA256 roles are separate

| Role | Meaning | Sent to server as expected hash? |
| --- | --- | --- |
| trusted / catalog `expectedSha256` | pinned in `DEFAULT_LORA_CATALOG` | yes — mismatch rejects the upload |
| learned `sha256` | computed by the server after a successful upload, stored back into the browser registration as metadata | **never** |

No catalog entry pins an `expectedSha256` today, so uploads are accepted and the
server returns the computed digest, which the browser records. A stale learned
hash in `localStorage` is never replayed as `expected_sha256` on the next
upload (this is the bug that previously rejected a re-exported file).

## `.upload.part` safety

- Each upload streams into a private temp file
  `"<name>.<pid>.<random>.upload.part"`.
- Only a fully received, SHA-checked file is `os.replace`-d onto the formal
  name (atomic).
- Success, client disconnect, cancellation and every exception path delete the
  temp file (`finally`).
- A per-filename `asyncio.Lock` serialises concurrent uploads of the same name;
  an in-flight upload never overwrites an existing good file mid-transfer.
- `_sweep_temp_files()` at process start removes any leftover
  `*.upload.part` / `*.part` (e.g. from a killed Pod).

## Pod re-creation (no Network Volume)

Terminating the Pod deletes the LoRA files. On a fresh Pod: registrations stay
in the browser, `/h3-mobile/api/loras/files` shows what is actually present,
missing LoRAs show `未導入`, and the user re-uploads the needed files (multi
select). No URL fallback.

## Full-settings backup (schema v3)

`全設定バックアップ` / `全設定を復元` — JSON only:

- projects (id, name, mode, refVariant, prompt, seconds, steps, megapixels,
  ratio, ref image size, seed, per-context LoRA enabled/strength/order)
- LoRA registry (id, name, filename, originalFilename, learned sha256,
  defaultStrength)
- generation presets

Not included: image binaries, LoRA binaries, IndexedDB image data, API keys,
URLs, model files. On restore, every project image reference is set to `null`
so a cross-device restore cannot point at a missing IndexedDB key — images are
re-picked by the user afterwards.

Legacy LoRA-only backup **v2** still imports; its `url` / `sourceType` /
`installMethod` / `pendingInstallMethod` / API-key fields are discarded.

## Ref2VA workflow model paths (unchanged, frozen)

- Ref2VA 04: UNET → AIO (0.40) → Motion Booster (0.50) → Sol-Attn → Balanced BlockCache
- Ref2VA 05: UNET → AIO (0.40) → Motion Booster (0.50) → SLA → Balanced BlockCache
- Ref2VA 06 fast: UNET → AIO (0.40) → Motion Booster (0.50) → SLA → Spectrum fast
- Ref2VA 06 stable: UNET → AIO (0.40) → Motion Booster (0.50) → SLA → Spectrum stable

| Workflow | Sampler | Scheduler | Steps | Shift | CFG |
| --- | --- | --- | ---: | --- | --- |
| Ref2VA 04 / 05 / 06 fast / 06 stable | euler | simple | 12 | N/A | N/A |

No shift input exists in these workflows; their `BasicGuider` nodes have no CFG
input. The two workflow-baked LoRA filenames
(`HMNSFW-AIO-V2.5.safetensors`, `H3_Motion_BoosterV2.safetensors`) must be
present in `ComfyUI/models/loras/`; upload them from the LoRA tab like any other
file.

## Prompt handling (unchanged)

Single and batch Ref2VA generation prepend `dynv2. ` exactly once, only when
Motion Booster (`Motion_REF2VA_v2.safetensors`) is enabled for the active
project. I2V and Motion-Booster-OFF prompts are untouched.

## Tests

Offline VM / static (all PASS locally, run in the `offline-tests` CI job):

- `tests/validate_lora_mobile_test.py`
- `tests/validate_lora_library.py`
- `tests/validate_lora_manager_v2.py`
- `tests/validate_lora_registration_cleanup.py`
- `tests/validate_lora_file_only.py` — state machine, error/retry, SHA
  separation, indeterminate-branch rendering, backup export/restore + v2
  migration. **Not** a progress-visibility proof (FakeXHR).
- `tests/validate_generation_presets.py`
- `tests/validate_ref2va06.py`
- `tests/validate_runtime_billing.py`

Plus `node --check` on the web JS, `python3 -m py_compile` on the route/test
modules, and `bash -n run.sh`.

Real browser (`browser-tests` CI job; `tests/validate_lora_upload_browser.py`
locally):

- `tests/integration_lora_upload_browser.mjs` — headless Chromium (Playwright)
  drives the real page against a local HTTP server with a deliberately **slow
  real multipart** `/loras/upload`. Asserts on the actual DOM:
  1. status is `アップロード中 0%` / `待機中` **synchronously** on file select
     (not `未導入`);
  2. the `.h3-lora-progress` bar element is present while uploading;
  3. progress text + bar width take many distinct values over the transfer
     (13 distinct values seen);
  4. `サーバー検証中` shows after the body is sent;
  5. ends at `✓ 導入済み`;
  6. the manager list is **never emptied**, including while `/loras/files`
     returns 500 throughout an upload, and recovers to `✓ 導入済み` afterwards;
  7. in a 2-file selection the pending file shows `待機中` while the first
     uploads.

Local real-browser status: **VERIFIED** (headless Chromium 151, 3 consecutive
clean runs). This does **not** cover RunPod proxy buffering of large multipart
uploads.

GitHub Actions: pending this push.
RunPod real-device test: **NOT STARTED**.
