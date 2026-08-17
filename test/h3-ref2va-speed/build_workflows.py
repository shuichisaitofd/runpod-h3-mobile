#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
OUT_DIR = HERE / "workflows"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_SPECTRUM = REPO_ROOT / "workflows" / "H3_Spectrum_SolAttn_16step.json"
BASE_TURBO = REPO_ROOT / "workflows" / "H3_TurboV4_SageAttention_4step.json"


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Base workflow not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save(data: dict, name: str) -> None:
    validate(data)
    path = OUT_DIR / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] built {path}")


def node_by_type(data: dict, type_name: str) -> dict:
    matches = [n for n in data.get("nodes", []) if n.get("type") == type_name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {type_name}, found {len(matches)}")
    return matches[0]


def set_steps(data: dict, steps: int) -> None:
    n = node_by_type(data, "BasicScheduler")
    vals = list(n.get("widgets_values") or [])
    if len(vals) < 3:
        vals = ["simple", steps, 1]
    else:
        vals[1] = steps
    n["widgets_values"] = vals


def set_save_prefix(data: dict, prefix: str) -> None:
    for n in data.get("nodes", []):
        if n.get("type") == "SaveVideo":
            vals = list(n.get("widgets_values") or [])
            if vals:
                vals[0] = f"video/{prefix}"
                n["widgets_values"] = vals


def enable_sol_int8_qk(data: dict) -> dict:
    sol = node_by_type(data, "MiniMaxH3MemoryEfficientSolAttentionPatch")
    vals = list(sol.get("widgets_values") or [])
    while len(vals) < 9:
        vals.append("")
    vals[0] = True
    vals[5] = True
    vals[6] = False
    vals[7] = "exact_kv"
    if vals[8] is None:
        vals[8] = ""
    sol["widgets_values"] = vals
    return sol


def replace_sage_with_sol(data: dict) -> dict:
    sage = node_by_type(data, "MiniMaxH3MemoryEfficientSageAttentionPatch")
    sage["type"] = "MiniMaxH3MemoryEfficientSolAttentionPatch"
    sage["size"] = [420, 270]
    sage["properties"] = {
        "Node name for S&R": "MiniMaxH3MemoryEfficientSolAttentionPatch",
        "aux_id": "Saganaki22/ComfyUI-sol-attn",
    }
    sage["widgets_values"] = [True, 1.3, 4096, False, "diag", True, False, "exact_kv", ""]
    return sage


def insert_fused_after(data: dict, upstream: dict) -> dict:
    model_out = next((o for o in upstream.get("outputs", []) if o.get("type") == "MODEL"), None)
    if model_out is None:
        raise RuntimeError(f"Node {upstream['id']} has no MODEL output")
    old_link_ids = list(model_out.get("links") or [])
    old_links = [l for l in data.get("links", []) if l[0] in old_link_ids]
    if not old_links:
        raise RuntimeError(f"Node {upstream['id']} has no downstream MODEL links")

    new_node_id = max(n["id"] for n in data["nodes"]) + 1
    new_link_to_fused = max(l[0] for l in data["links"]) + 1
    fused = {
        "id": new_node_id,
        "type": "MiniMaxH3FusedModulation",
        "pos": [upstream.get("pos", [0, 0])[0] + 500, upstream.get("pos", [0, 0])[1]],
        "size": [330, 90],
        "flags": {},
        "order": upstream.get("order", 0) + 1,
        "mode": 0,
        "inputs": [{"name": "model", "type": "MODEL", "link": new_link_to_fused}],
        "outputs": [{"name": "model", "type": "MODEL", "links": old_link_ids}],
        "properties": {
            "Node name for S&R": "MiniMaxH3FusedModulation",
            "aux_id": "Saganaki22/ComfyUI-sol-attn",
        },
        "widgets_values": [True],
    }

    for l in old_links:
        l[1] = new_node_id
        l[2] = 0
    model_out["links"] = [new_link_to_fused]
    data["links"].append([new_link_to_fused, upstream["id"], 0, new_node_id, 0, "MODEL"])
    data["nodes"].append(fused)
    data["last_node_id"] = max(data.get("last_node_id", 0), new_node_id)
    data["last_link_id"] = max(data.get("last_link_id", 0), new_link_to_fused)
    return fused


def replace_spectrum_with_accelerator(data: dict) -> dict:
    spectrum = node_by_type(data, "SpectrumApplyMiniMaxH3")
    spectrum["type"] = "ApplyH3Ref2VAUltraSafeBlockCache"
    spectrum["size"] = [430, 410]
    spectrum["properties"] = {
        "Node name for S&R": "ApplyH3Ref2VAUltraSafeBlockCache",
        "aux_id": "BMB12d3/ComfyUI-H3-Ref2VA-Accelerator",
    }
    spectrum["widgets_values"] = [
        "Ref2VA Balanced",
        "CPU (VRAM-safe)",
        False,
        False,
        0.090,
        0.090,
        0.080,
        0.065,
        0.065,
        0.110,
        0.10,
        0.95,
        1,
        "Safe CPU (v0.3 behavior)",
    ]
    return spectrum


def validate(data: dict) -> None:
    ids = {n["id"] for n in data.get("nodes", [])}
    links = data.get("links", [])
    link_ids = {l[0] for l in links}
    if len(link_ids) != len(links):
        raise RuntimeError("duplicate link id")
    for l in links:
        if l[1] not in ids or l[3] not in ids:
            raise RuntimeError(f"dangling link: {l}")
    for n in data.get("nodes", []):
        for inp in n.get("inputs", []):
            lid = inp.get("link")
            if lid is not None and lid not in link_ids:
                raise RuntimeError(f"node {n['id']} has missing input link {lid}")
        for out in n.get("outputs", []):
            for lid in out.get("links") or []:
                if lid not in link_ids:
                    raise RuntimeError(f"node {n['id']} has missing output link {lid}")
    if links and data.get("last_link_id", 0) < max(link_ids):
        raise RuntimeError("last_link_id is stale")


def build_02() -> dict:
    data = copy.deepcopy(load(BASE_SPECTRUM))
    sol = enable_sol_int8_qk(data)
    insert_fused_after(data, sol)
    set_steps(data, 12)
    set_save_prefix(data, "R2V_TEST_02_SPECTRUM_ENHANCED")
    data.setdefault("extra", {})["workflow_name"] = "R2V 02 - Spectrum + Sol int8_qk + Fused Modulation"
    return data


def build_03() -> dict:
    data = copy.deepcopy(load(BASE_TURBO))
    sol = replace_sage_with_sol(data)
    insert_fused_after(data, sol)
    set_steps(data, 10)
    set_save_prefix(data, "R2V_TEST_03_TURBO_ENHANCED")
    data.setdefault("extra", {})["workflow_name"] = "R2V 03 - Turbo + Sol int8_qk + Fused Modulation"
    return data


def build_04() -> dict:
    data = copy.deepcopy(load(BASE_SPECTRUM))
    replace_spectrum_with_accelerator(data)
    enable_sol_int8_qk(data)
    set_steps(data, 12)
    set_save_prefix(data, "R2V_TEST_04_ACCELERATOR_BALANCED")
    data.setdefault("extra", {})["workflow_name"] = "R2V 04 - Accelerator Balanced + Sol int8_qk"
    return data


if __name__ == "__main__":
    save(build_02(), "02_SPECTRUM_ENHANCED_WORKFLOW.json")
    save(build_03(), "03_TURBO_ENHANCED_WORKFLOW.json")
    save(build_04(), "04_ACCELERATOR_BALANCED_SOL_WORKFLOW.json")
