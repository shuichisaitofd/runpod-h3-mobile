# H3 Ref2VA speed-test kit

This directory is test-only. It does not change the normal Docker image or `main` branch.

## Purpose

Reproduce the 2026-08 Ref2VA acceleration tests without repeating the setup failures from the first session.

Test branches:
- 02: Spectrum + Sol-Attn (`int8_qk`) + Fused Modulation
- 03: Turbo LoRA + Turbo Sampler + Sol-Attn (`int8_qk`) + Fused Modulation
- 04: Ref2VA Accelerator Balanced + Sol-Attn (`int8_qk`)

## Important fixed issue

Upstream `ComfyUI-H3-Ref2VA-Accelerator` v0.4.2 commit `b3299ac7...` contains a broken `decide()` source line. The required assignment to `context.first_block_output` is missing from executable code, causing:

`H3 Ref2VA Block Cache full-step state is incomplete`

`setup_test.sh` pins that exact upstream commit and applies `patches/h3_ref2va_accelerator_first_block_output_fix.patch` before ComfyUI is restarted.

Do not use `Auto GPU Fast Path` for this comparison. Use `Safe CPU (v0.3 behavior)`.

## Next Pod: exact sequence

From a normal H3 Pod created with the existing production image:

```bash
cd /workspace
git clone --branch test/h3-ref2va-speed --single-branch https://github.com/shuichisaitofd/runpod-h3-mobile.git h3-speed-test
cd /workspace/h3-speed-test/test/h3-ref2va-speed
bash setup_test.sh
bash check_test.sh
bash restart_comfy_test.sh
```

Then refresh Port 8188 and open the workflows under `H3_REF2VA_SPEED_TEST`.

## Test approach

Keep the same references, seed, MP, duration and prompt. Change only acceleration method and STEP.

Recommended next checks based on the first session:
- 02 Spectrum: 10 / 12 / 16 STEP. 20 STEP did not visibly improve quality in the first session.
- 03 Turbo: start around 10 STEP, then test 8 / 6 if reference fidelity remains strong.
- 04 Accelerator: first confirm a clean run after the code patch, then compare at the same STEP as 02.

Observed first-session tendency (manual observation, not a controlled benchmark):
- 02 was faster than the previous current configuration while looking very similar.
- 03 preserved the reference/background more strongly, but was slower at higher STEP.
- 02 quality did not visibly improve when raised from 16 to 20 STEP.

## Before terminating the Pod

```bash
cd /workspace/h3-speed-test/test/h3-ref2va-speed
bash collect_results.sh
```

If FileBrowser/Jupyter are unavailable, the script prints the archive path. To expose the latest archive through the already-public 8188 port:

```bash
bash serve_results.sh /workspace/H3_TEST_RESULTS_YYYYMMDD_HHMMSS.tar.gz
```

Then open RunPod `Port 8188` and download the single `.tar.gz` file. This intentionally stops ComfyUI only at the final download stage.
