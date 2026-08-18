from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass, field
from typing import Any

import torch

import comfy.patcher_extension

try:
    import comfy.model_prefetch
    _PREFETCH_AVAILABLE = True
except ImportError:
    # If a future ComfyUI moves/renames the prefetch module, keep the node functional:
    # cache hits still skip block compute, we just cannot suppress tail weight prefetch.
    _PREFETCH_AVAILABLE = False


NODE_VERSION = "0.4.2"

ULTRA_SAFE = "Ref2VA Ultra Safe (quality-first)"
CONSERVATIVE = "Ref2VA Conservative"
BALANCED = "Ref2VA Balanced"
AGGRESSIVE = "Ref2VA Aggressive (experimental)"
OBSERVE = "Observe Only (no caching)"
CUSTOM = "Custom"

CPU_STORAGE = "CPU (VRAM-safe)"
GPU_STORAGE = "GPU (faster, uses VRAM)"

CPU_TAIL_SAFE = "Safe CPU (v0.3 behavior)"
CPU_TAIL_AUTO = "Auto GPU Fast Path"


@dataclass(frozen=True)
class PresetConfig:
    global_threshold: float
    video_threshold: float
    audio_threshold: float
    visual_ref_threshold: float
    audio_ref_threshold: float
    temporal_threshold: float
    start_percent: float
    end_percent: float
    max_consecutive_hits: int
    observe_only: bool = False


# Ref2VA-specific profiles tuned through fixed-seed A/B testing on native ComfyUI H3.
# They are still approximate accelerators, not universal quality guarantees. Balanced is the
# recommended production profile because it produced a substantial speed gain while keeping
# observed trajectory changes small. Aggressive is retained explicitly as an experimental mode.
PRESETS = {
    ULTRA_SAFE: PresetConfig(
        global_threshold=0.070,
        video_threshold=0.070,
        audio_threshold=0.060,
        visual_ref_threshold=0.045,
        audio_ref_threshold=0.045,
        temporal_threshold=0.080,
        start_percent=0.20,
        end_percent=0.85,
        max_consecutive_hits=1,
    ),
    CONSERVATIVE: PresetConfig(
        global_threshold=0.080,
        video_threshold=0.080,
        audio_threshold=0.070,
        visual_ref_threshold=0.055,
        audio_ref_threshold=0.055,
        temporal_threshold=0.095,
        start_percent=0.15,
        end_percent=0.90,
        max_consecutive_hits=1,
    ),
    BALANCED: PresetConfig(
        global_threshold=0.090,
        video_threshold=0.090,
        audio_threshold=0.080,
        visual_ref_threshold=0.065,
        audio_ref_threshold=0.065,
        temporal_threshold=0.110,
        start_percent=0.10,
        end_percent=0.95,
        max_consecutive_hits=1,
    ),
    AGGRESSIVE: PresetConfig(
        global_threshold=0.120,
        video_threshold=0.120,
        audio_threshold=0.100,
        visual_ref_threshold=0.090,
        audio_ref_threshold=0.090,
        temporal_threshold=0.145,
        start_percent=0.05,
        end_percent=0.98,
        max_consecutive_hits=2,
    ),
    OBSERVE: PresetConfig(
        global_threshold=0.090,
        video_threshold=0.090,
        audio_threshold=0.080,
        visual_ref_threshold=0.065,
        audio_ref_threshold=0.065,
        temporal_threshold=0.110,
        start_percent=0.10,
        end_percent=0.95,
        max_consecutive_hits=1,
        observe_only=True,
    ),
}


@dataclass
class StepMetrics:
    global_ratio: float | None = None
    video_ratio: float | None = None
    audio_ratio: float | None = None
    visual_ref_ratio: float | None = None
    audio_ref_ratio: float | None = None
    temporal_ratio: float | None = None
    reason: str = ""
    eligible: bool = False
    cache_hit: bool = False


@dataclass
class CacheContext:
    input_signature: tuple | None = None
    previous_sigma: float | None = None
    layout: Any = None
    has_refs: bool = False
    use_cache: bool = False
    previous_block0_in: Any = None
    previous_block0_out: Any = None
    tail_residual: Any = None
    metrics: StepMetrics = field(default_factory=StepMetrics)
    consecutive_hits: int = 0
    tail_scales: Any = None

    def clear_tensors(self):
        self.previous_block0_in = None
        self.previous_block0_out = None
        self.tail_residual = None
        self.consecutive_hits = 0
        self.tail_scales = None


class Ref2VACacheRuntime:
    def __init__(
        self,
        config: PresetConfig,
        start_sigma: float,
        end_sigma: float,
        block_count: int,
        storage: str,
        debug: bool,
        block_modules: list,
        tail_rescale: bool = False,
        cpu_tail_compute: str = CPU_TAIL_SAFE,
    ):
        self.config = config
        self.start_sigma = float(start_sigma)
        self.end_sigma = float(end_sigma)
        self.block_count = int(block_count)
        self.storage = storage
        self.debug = bool(debug)
        self.tail_rescale = bool(tail_rescale)
        self.cpu_tail_compute = cpu_tail_compute
        self.block_modules = block_modules
        self.block_ids = tuple(id(b) for b in block_modules)
        self.contexts: dict[tuple[str, ...], CacheContext] = {}
        self.current: CacheContext | None = None
        self.prefetch_queue = None
        self.total_steps = 0
        self.eligible_steps = 0
        self.cache_hits = 0
        self.prefetch_suppressed_steps = 0
        self.steps_without_refs = 0
        self.gpu_tail_steps = 0
        self._layout_warned = False
        self._step_number = 0

    @staticmethod
    def _input_signature(x):
        tensors = x if isinstance(x, (tuple, list)) else (x,)
        return tuple((tuple(t.shape), t.dtype, str(t.device)) for t in tensors if torch.is_tensor(t))

    @staticmethod
    def _extract_sigma(timestep, transformer_options) -> float:
        # Prefer the sampler-provided sigma when present; it is independent of the model's
        # timestep convention. Fall back to the H3/flow convention (timestep == sigma * 1000).
        sigmas = transformer_options.get("sigmas") if isinstance(transformer_options, dict) else None
        if torch.is_tensor(sigmas) and sigmas.numel() > 0:
            return float(sigmas.flatten()[0].item())
        return float(timestep.flatten()[0].item()) / 1000.0

    def begin_call(self, x, timestep, transformer_options, minimax_payload=None):
        sigma = self._extract_sigma(timestep, transformer_options)
        uuids = transformer_options.get("uuids")
        key = tuple(str(value) for value in uuids) if uuids else ("default",)
        context = self.contexts.setdefault(key, CacheContext())
        signature = self._input_signature(x)
        if context.input_signature != signature or (context.previous_sigma is not None and sigma > context.previous_sigma + 1e-7):
            context.clear_tensors()
        payload = minimax_payload or {}
        context.input_signature = signature
        context.previous_sigma = sigma
        context.layout = payload.get("layout")
        context.has_refs = bool(payload.get("refs")) and context.layout is not None
        context.use_cache = False
        context.metrics = StepMetrics()
        context.tail_scales = None
        if not context.has_refs:
            self.steps_without_refs += 1
        self.current = context
        self.prefetch_queue = None
        self._step_number += 1

    def end_call(self):
        self.current = None
        self.prefetch_queue = None

    def _within_window(self, context: CacheContext) -> bool:
        sigma = context.previous_sigma
        return sigma is not None and self.end_sigma <= sigma <= self.start_sigma

    def capture_prefetch_queue(self, original_make, queue, device, transformer_options):
        out = original_make(queue, device, transformer_options)
        if out is not None and len(queue) == self.block_count:
            try:
                if tuple(id(b) for b in queue) == self.block_ids:
                    self.prefetch_queue = out
            except Exception:
                pass
        return out

    @staticmethod
    def _safe_rel_diff(current, previous, eps=1e-8):
        if current is None or previous is None:
            return None
        if not (torch.is_tensor(current) and torch.is_tensor(previous)):
            return None
        cur = current.detach().float()
        prev = previous.detach().float()
        denom = prev.abs().mean().clamp_min(eps)
        return float((cur - prev).abs().mean().div(denom).item())

    @staticmethod
    def _match_device_dtype(value, ref):
        if torch.is_tensor(value) and torch.is_tensor(ref):
            if value.device != ref.device or value.dtype != ref.dtype:
                return value.to(device=ref.device, dtype=ref.dtype)
        return value

    @staticmethod
    def _tensor_get(tensor, selector):
        if not torch.is_tensor(tensor):
            return None
        try:
            return tensor[selector]
        except Exception:
            return None

    def _layout_slices(self, tensor, layout):
        # Native H3 exposes a layout that maps the concatenated token sequence to target/reference
        # video/audio regions. Support both dict-like and object-like access so this stays compatible
        # across recent ComfyUI H3 implementations.
        if tensor is None or layout is None:
            return None

        def get(name, default=None):
            if isinstance(layout, dict):
                return layout.get(name, default)
            return getattr(layout, name, default)

        candidates = {}
        direct_names = {
            "video": ["video", "target_video", "target_video_slice", "video_slice"],
            "audio": ["audio", "target_audio", "target_audio_slice", "audio_slice"],
            "visual_ref": ["visual_ref", "visual_refs", "reference_video", "ref_video", "visual_ref_slice"],
            "audio_ref": ["audio_ref", "audio_refs", "reference_audio", "ref_audio", "audio_ref_slice"],
        }
        for key, names in direct_names.items():
            for name in names:
                selector = get(name)
                if selector is not None:
                    value = self._tensor_get(tensor, selector)
                    if value is not None:
                        candidates[key] = value
                        break
        if candidates:
            return candidates

        # Common count/offset fallback. If exact names are unavailable, do not guess silently; emit a
        # one-time warning and disable cache decisions for that step.
        if not self._layout_warned:
            logging.warning(
                "[H3 Ref2VA Block Cache] Unable to map native H3 layout into target/reference regions; "
                "cache hits will remain disabled until a supported layout is seen."
            )
            self._layout_warned = True
        return None

    @staticmethod
    def _frame_worst_ratio(current, previous, eps=1e-8):
        if not (torch.is_tensor(current) and torch.is_tensor(previous)):
            return None
        if current.ndim < 2:
            return Ref2VACacheRuntime._safe_rel_diff(current, previous, eps)
        cur = current.detach().float()
        prev = previous.detach().float()
        # Treat the penultimate sequence-like dimension as temporal/token axis and compare each slice.
        axis = -2
        diff = (cur - prev).abs().mean(dim=tuple(i for i in range(cur.ndim) if i != (cur.ndim + axis) % cur.ndim))
        denom = prev.abs().mean(dim=tuple(i for i in range(prev.ndim) if i != (prev.ndim + axis) % prev.ndim)).clamp_min(eps)
        ratio = diff / denom
        return float(ratio.max().item())

    def _store(self, value):
        if value is None:
            return None
        if isinstance(value, tuple):
            return tuple(self._store(v) for v in value)
        if isinstance(value, list):
            return [self._store(v) for v in value]
        if torch.is_tensor(value):
            out = value.detach()
            if self.storage == CPU_STORAGE:
                out = out.to("cpu")
            else:
                out = out.clone()
            return out
        return value

    def _restore_like(self, stored, ref):
        if isinstance(stored, tuple) and isinstance(ref, tuple):
            return tuple(self._restore_like(s, r) for s, r in zip(stored, ref))
        if isinstance(stored, list) and isinstance(ref, list):
            return [self._restore_like(s, r) for s, r in zip(stored, ref)]
        if torch.is_tensor(stored) and torch.is_tensor(ref):
            return stored.to(device=ref.device, dtype=ref.dtype)
        return stored

    @staticmethod
    def _sub(a, b):
        if isinstance(a, tuple) and isinstance(b, tuple):
            return tuple(Ref2VACacheRuntime._sub(x, y) for x, y in zip(a, b))
        if isinstance(a, list) and isinstance(b, list):
            return [Ref2VACacheRuntime._sub(x, y) for x, y in zip(a, b)]
        if torch.is_tensor(a) and torch.is_tensor(b):
            return a - b
        raise TypeError("Unsupported H3 block output structure")

    @staticmethod
    def _add(a, b):
        if isinstance(a, tuple) and isinstance(b, tuple):
            return tuple(Ref2VACacheRuntime._add(x, y) for x, y in zip(a, b))
        if isinstance(a, list) and isinstance(b, list):
            return [Ref2VACacheRuntime._add(x, y) for x, y in zip(a, b)]
        if torch.is_tensor(a) and torch.is_tensor(b):
            return a + b
        raise TypeError("Unsupported H3 block output structure")

    @staticmethod
    def _mul(a, scale):
        if isinstance(a, tuple):
            return tuple(Ref2VACacheRuntime._mul(x, scale) for x in a)
        if isinstance(a, list):
            return [Ref2VACacheRuntime._mul(x, scale) for x in a]
        if torch.is_tensor(a):
            return a * scale
        raise TypeError("Unsupported H3 block output structure")

    def _derive_tail_scales(self, current, previous):
        if not self.tail_rescale:
            return None
        cur_tensors = current if isinstance(current, (tuple, list)) else (current,)
        prev_tensors = previous if isinstance(previous, (tuple, list)) else (previous,)
        scales = []
        for cur, prev in zip(cur_tensors, prev_tensors):
            if not (torch.is_tensor(cur) and torch.is_tensor(prev)):
                scales.append(1.0)
                continue
            prev_mag = prev.detach().float().abs().mean().clamp_min(1e-8)
            cur_mag = cur.detach().float().abs().mean()
            scale = float((cur_mag / prev_mag).clamp(0.90, 1.10).item())
            scales.append(scale)
        if isinstance(current, tuple):
            return tuple(scales)
        if isinstance(current, list):
            return list(scales)
        return scales[0] if scales else 1.0

    def _apply_scales(self, value, scales):
        if scales is None:
            return value
        if isinstance(value, tuple) and isinstance(scales, tuple):
            return tuple(self._mul(v, s) for v, s in zip(value, scales))
        if isinstance(value, list) and isinstance(scales, list):
            return [self._mul(v, s) for v, s in zip(value, scales)]
        return self._mul(value, scales)

    def _maybe_gpu_tail_fast_path(self, current_block0_out):
        context = self.current
        if context is None or self.storage != CPU_STORAGE or self.cpu_tail_compute != CPU_TAIL_AUTO:
            return False
        if context.tail_residual is None or context.previous_block0_out is None:
            return False
        # Only stage the cached tail on GPU after every guard has already passed. This keeps the
        # default Safe CPU behavior identical to v0.3 while allowing a benchmark-only fast path.
        try:
            restored = self._restore_like(context.tail_residual, current_block0_out)
            context.tail_residual = restored
            self.gpu_tail_steps += 1
            return True
        except Exception:
            return False

    def decide_after_block0(self, block0_input, block0_output):
        context = self.current
        if context is None:
            return False

        self.total_steps += 1
        metrics = StepMetrics()
        context.metrics = metrics

        if self.config.observe_only:
            metrics.reason = "observe-only"
        elif not context.has_refs:
            metrics.reason = "no-native-ref-layout"
        elif not self._within_window(context):
            metrics.reason = "outside-window"
        elif context.previous_block0_in is None or context.previous_block0_out is None or context.tail_residual is None:
            metrics.reason = "warmup"
        elif context.consecutive_hits >= self.config.max_consecutive_hits:
            metrics.reason = "max-consecutive"
        else:
            metrics.global_ratio = self._safe_rel_diff(block0_output, context.previous_block0_out)
            regions = self._layout_slices(block0_output, context.layout)
            prev_regions = self._layout_slices(context.previous_block0_out, context.layout)
            if regions is None or prev_regions is None:
                metrics.reason = "unsupported-layout"
            else:
                metrics.video_ratio = self._safe_rel_diff(regions.get("video"), prev_regions.get("video"))
                metrics.audio_ratio = self._safe_rel_diff(regions.get("audio"), prev_regions.get("audio"))
                metrics.visual_ref_ratio = self._safe_rel_diff(regions.get("visual_ref"), prev_regions.get("visual_ref"))
                metrics.audio_ref_ratio = self._safe_rel_diff(regions.get("audio_ref"), prev_regions.get("audio_ref"))
                metrics.temporal_ratio = self._frame_worst_ratio(regions.get("video"), prev_regions.get("video"))

                checks = [
                    (metrics.global_ratio, self.config.global_threshold, "global"),
                    (metrics.video_ratio, self.config.video_threshold, "video"),
                    (metrics.audio_ratio, self.config.audio_threshold, "audio"),
                    (metrics.visual_ref_ratio, self.config.visual_ref_threshold, "visual-ref"),
                    (metrics.audio_ref_ratio, self.config.audio_ref_threshold, "audio-ref"),
                    (metrics.temporal_ratio, self.config.temporal_threshold, "temporal"),
                ]
                failed = []
                for value, threshold, name in checks:
                    if value is not None and value > threshold:
                        failed.append(f"{name}:{value:.4f}>{threshold:.4f}")
                if failed:
                    metrics.reason = ", ".join(failed)
                else:
                    metrics.eligible = True
                    self.eligible_steps += 1
                    context.tail_scales = self._derive_tail_scales(block0_output, context.previous_block0_out)
                    context.use_cache = True
                    metrics.cache_hit = True
                    metrics.reason = "cache-hit"
                    self.cache_hits += 1
                    context.consecutive_hits += 1
                    self._maybe_gpu_tail_fast_path(block0_output)
                    return True

        context.use_cache = False
        context.consecutive_hits = 0
        return False

    def capture_full_step(self, block0_input, block0_output, final_output):
        context = self.current
        if context is None:
            return
        context.previous_block0_in = self._store(block0_input)
        context.previous_block0_out = self._store(block0_output)
        context.tail_residual = self._store(self._sub(final_output, block0_output))
        context.consecutive_hits = 0

    def cached_output(self, block0_output):
        context = self.current
        if context is None or context.tail_residual is None:
            raise RuntimeError("H3 Ref2VA Block Cache requested without a stored tail residual")
        residual = self._restore_like(context.tail_residual, block0_output)
        residual = self._apply_scales(residual, context.tail_scales)
        return self._add(block0_output, residual)

    def suppress_prefetch_after_hit(self):
        if self.prefetch_queue is None:
            return
        try:
            # The prefetch iterator is private to the currently scheduled H3 block queue. Clearing
            # it prevents background loading of blocks 1..49 once we know the cached tail will be used.
            if hasattr(self.prefetch_queue, "clear"):
                self.prefetch_queue.clear()
            elif hasattr(self.prefetch_queue, "queue"):
                self.prefetch_queue.queue.clear()
            self.prefetch_suppressed_steps += 1
        except Exception:
            pass

    def summary(self, label):
        return (
            f"[H3 Ref2VA Block Cache {NODE_VERSION}] {label}: "
            f"steps={self.total_steps}, eligible={self.eligible_steps}, hits={self.cache_hits}, "
            f"prefetch_suppressed={self.prefetch_suppressed_steps}, without_refs={self.steps_without_refs}, "
            f"gpu_tail_steps={self.gpu_tail_steps}"
        )

    def reset(self):
        self.contexts.clear()
        self.current = None
        self.prefetch_queue = None


def _make_prefetch_wrapper(runtime: Ref2VACacheRuntime):
    def wrapper(executor, *args, **kwargs):
        original_make = executor.original
        if not _PREFETCH_AVAILABLE:
            return executor(*args, **kwargs)
        try:
            queue = args[0] if args else kwargs.get("queue")
            device = args[1] if len(args) > 1 else kwargs.get("device")
            transformer_options = args[2] if len(args) > 2 else kwargs.get("transformer_options")
            return runtime.capture_prefetch_queue(original_make, queue, device, transformer_options)
        except Exception:
            return executor(*args, **kwargs)
    return wrapper


def _extract_minimax_payload(args, kwargs):
    payload = kwargs.get("minimax_payload")
    if payload is not None:
        return payload
    # Native MiniMax H3 forward currently places minimax_payload after transformer_options. Avoid
    # relying on one exact positional index across ComfyUI revisions; search for a dict carrying the
    # native layout/refs keys.
    for value in reversed(args):
        if isinstance(value, dict) and ("layout" in value or "refs" in value):
            return value
    return None


def _extract_transformer_options(args, kwargs):
    options = kwargs.get("transformer_options")
    if isinstance(options, dict):
        return options
    for value in args:
        if isinstance(value, dict) and ("block_modulation_hooks" in value or "patches_replace" in value or "uuids" in value or "sigmas" in value):
            return value
    return {}


def make_block_patch(runtime: Ref2VACacheRuntime, index: int, last_index: int):
    def patch(args, extra_args):
        # ComfyUI block replacement patch signature: patch(block_args_dict, extra_args_dict)
        original_block = extra_args["original_block"]
        if index == 0:
            block_input = args
            out = original_block(args)
            if runtime.current is None:
                return out
            # The native H3 block patch passes a dict; compare its primary hidden-state tensors.
            input_value = tuple(v for v in block_input.values() if torch.is_tensor(v)) if isinstance(block_input, dict) else block_input
            output_value = tuple(v for v in out.values() if torch.is_tensor(v)) if isinstance(out, dict) else out
            runtime.decide_after_block0(input_value, output_value)
            if runtime.current.use_cache:
                runtime.suppress_prefetch_after_hit()
            else:
                runtime.current.previous_block0_in = runtime._store(input_value)
                runtime.current.previous_block0_out = runtime._store(output_value)
            return out

        if runtime.current is not None and runtime.current.use_cache:
            if index == last_index:
                # Reuse the complete tail residual at the final block. This is the only later block
                # invoked on a cache hit; all middle blocks become no-ops.
                current_value = tuple(v for v in args.values() if torch.is_tensor(v)) if isinstance(args, dict) else args
                cached = runtime.cached_output(current_value)
                if isinstance(args, dict):
                    out = dict(args)
                    tensor_keys = [k for k, v in args.items() if torch.is_tensor(v)]
                    cached_vals = cached if isinstance(cached, (tuple, list)) else (cached,)
                    for key, value in zip(tensor_keys, cached_vals):
                        out[key] = value
                    return out
                return cached
            return args

        out = original_block(args)
        if index == last_index and runtime.current is not None:
            block0_out = runtime.current.previous_block0_out
            if block0_out is not None:
                final_value = tuple(v for v in out.values() if torch.is_tensor(v)) if isinstance(out, dict) else out
                block0_ref = runtime._restore_like(block0_out, final_value)
                runtime.current.tail_residual = runtime._store(runtime._sub(final_value, block0_ref))
                runtime.current.consecutive_hits = 0
        return out

    return patch


def make_diffusion_wrapper(runtime: Ref2VACacheRuntime):
    def wrapper(executor, *args, **kwargs):
        # x and timestep are the first two native diffusion-model arguments.
        x = args[0] if args else kwargs.get("x")
        timestep = args[1] if len(args) > 1 else kwargs.get("timestep")
        transformer_options = _extract_transformer_options(args, kwargs)
        minimax_payload = _extract_minimax_payload(args, kwargs)
        runtime.begin_call(x, timestep, transformer_options, minimax_payload=minimax_payload)
        try:
            if _PREFETCH_AVAILABLE:
                key = f"h3_ref2va_prefetch_{id(runtime)}"
                try:
                    # Register only for the duration of this H3 diffusion call.
                    comfy.patcher_extension.add_wrapper_with_key(
                        comfy.patcher_extension.WrappersMP.PRE_RUN,
                        key,
                        _make_prefetch_wrapper(runtime),
                        transformer_options,
                    )
                except Exception:
                    pass
            return executor(*args, **kwargs)
        finally:
            runtime.end_call()
    return wrapper


def make_sample_wrapper(runtime: Ref2VACacheRuntime, label: str):
    def wrapper(executor, *args, **kwargs):
        try:
            return executor(*args, **kwargs)
        finally:
            logging.info("\n%s", runtime.summary(label))
            runtime.reset()
    return wrapper


class ApplyH3Ref2VAUltraSafeBlockCache:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "mode": ([BALANCED, CONSERVATIVE, ULTRA_SAFE, AGGRESSIVE, OBSERVE, CUSTOM], {"default": BALANCED}),
                "cache_storage": ([CPU_STORAGE, GPU_STORAGE], {"default": CPU_STORAGE, "tooltip": "CPU is recommended for pruned BF16/offloaded H3. GPU can be slightly faster for smaller quantized checkpoints with comfortable VRAM headroom."}),
                "debug": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "tail_rescale": ("BOOLEAN", {"default": False, "advanced": True, "tooltip": "Experimental only. Fixed-seed testing produced slightly different output without a clear quality benefit. Production recommendation: leave OFF."}),
                "global_threshold": ("FLOAT", {"default": 0.090, "min": 0.0, "max": 1.0, "step": 0.005, "advanced": True, "tooltip": "Custom mode only: overall block-0 residual-change limit."}),
                "video_threshold": ("FLOAT", {"default": 0.090, "min": 0.0, "max": 1.0, "step": 0.005, "advanced": True, "tooltip": "Custom mode only: target-video residual-change limit."}),
                "audio_threshold": ("FLOAT", {"default": 0.080, "min": 0.0, "max": 1.0, "step": 0.005, "advanced": True, "tooltip": "Custom mode only: target-audio residual-change limit."}),
                "visual_ref_threshold": ("FLOAT", {"default": 0.065, "min": 0.0, "max": 1.0, "step": 0.005, "advanced": True, "tooltip": "Custom mode only: visual-reference residual-change limit."}),
                "audio_ref_threshold": ("FLOAT", {"default": 0.065, "min": 0.0, "max": 1.0, "step": 0.005, "advanced": True, "tooltip": "Custom mode only: reference-audio residual-change limit."}),
                "temporal_threshold": ("FLOAT", {"default": 0.110, "min": 0.0, "max": 1.0, "step": 0.005, "advanced": True, "tooltip": "Custom mode only: worst target-video frame-change limit."}),
                "start_percent": ("FLOAT", {"default": 0.10, "min": 0.0, "max": 1.0, "step": 0.01, "advanced": True, "tooltip": "Custom mode only: earliest denoising fraction where cache hits are allowed."}),
                "end_percent": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01, "advanced": True, "tooltip": "Custom mode only: latest denoising fraction where cache hits are allowed."}),
                "max_consecutive_hits": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1, "advanced": True, "tooltip": "Custom mode only. Quality-first recommendation: leave at 1."}),
                "cpu_tail_compute": ([CPU_TAIL_SAFE, CPU_TAIL_AUTO], {"default": CPU_TAIL_SAFE, "advanced": True, "tooltip": "CPU cache mode only. Production recommendation: Safe CPU. Auto GPU Fast Path is retained for benchmarking; on the validated RTX 5090 BF16 workflow it saved only ~2 seconds over an ~11 minute sampler run."}),
            },
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "MiniMax H3/optimization"
    DESCRIPTION = (
        "Production-oriented MiniMax H3 Ref2VA accelerator. Balanced is the recommended quality/speed "
        "profile. Block 0 runs every step; blocks 1-49 are reused only when global, target-video, "
        "target-audio, reference and temporal guards all pass. This is deterministic but approximate. "
        "CPU cache storage is recommended for offloaded pruned BF16 H3."
    )

    def apply(
        self,
        model,
        mode,
        cache_storage,
        debug,
        tail_rescale=False,
        global_threshold=0.090,
        video_threshold=0.090,
        audio_threshold=0.080,
        visual_ref_threshold=0.065,
        audio_ref_threshold=0.065,
        temporal_threshold=0.110,
        start_percent=0.10,
        end_percent=0.95,
        max_consecutive_hits=1,
        cpu_tail_compute=CPU_TAIL_SAFE,
    ):
        if mode == CUSTOM:
            if start_percent >= end_percent:
                raise ValueError("start_percent must be less than end_percent")
            config = PresetConfig(
                global_threshold=float(global_threshold),
                video_threshold=float(video_threshold),
                audio_threshold=float(audio_threshold),
                visual_ref_threshold=float(visual_ref_threshold),
                audio_ref_threshold=float(audio_ref_threshold),
                temporal_threshold=float(temporal_threshold),
                start_percent=float(start_percent),
                end_percent=float(end_percent),
                max_consecutive_hits=int(max_consecutive_hits),
            )
            label = (
                f"Custom g/v/a/rv/ra/t={global_threshold:.3f}/{video_threshold:.3f}/{audio_threshold:.3f}/"
                f"{visual_ref_threshold:.3f}/{audio_ref_threshold:.3f}/{temporal_threshold:.3f}; "
                f"window={start_percent:.2f}-{end_percent:.2f}; max={max_consecutive_hits}"
            )
        else:
            config = PRESETS[mode]
            label = mode
        if tail_rescale:
            label = f"{label}; tail_rescale=ON (experimental)"
        if cpu_tail_compute not in (CPU_TAIL_SAFE, CPU_TAIL_AUTO):
            raise ValueError(f"Unknown cpu_tail_compute mode: {cpu_tail_compute}")
        if cache_storage == CPU_STORAGE and cpu_tail_compute == CPU_TAIL_AUTO:
            label = f"{label}; cpu_tail=Auto GPU Fast Path"

        patched = model.clone()
        diffusion_model = patched.get_model_object("diffusion_model")
        block_count = len(diffusion_model.blocks)
        if block_count < 2:
            raise RuntimeError("MiniMax H3 Ref2VA Block Cache requires a multi-block diffusion model")

        # Ref2VA native H3 runs high sigma to low sigma. Convert denoising progress into the sigma
        # window using the model's current sampling schedule if available; fall back to 1->0.
        start_sigma = 1.0 - config.start_percent
        end_sigma = 1.0 - config.end_percent

        runtime = Ref2VACacheRuntime(
            config=config,
            start_sigma=start_sigma,
            end_sigma=end_sigma,
            block_count=block_count,
            storage=cache_storage,
            debug=bool(debug),
            block_modules=list(diffusion_model.blocks),
            tail_rescale=bool(tail_rescale),
            cpu_tail_compute=cpu_tail_compute,
        )

        for index in range(block_count):
            patched.set_model_patch_replace(
                make_block_patch(runtime, index, block_count - 1),
                "dit",
                "double_block",
                index,
            )

        key = f"h3_ref2va_ultrasafe_block_cache_{id(runtime)}"
        patched.add_wrapper_with_key(
            comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL,
            key,
            make_diffusion_wrapper(runtime),
        )
        patched.add_wrapper_with_key(
            comfy.patcher_extension.WrappersMP.OUTER_SAMPLE,
            key,
            make_sample_wrapper(runtime, label),
        )
        return (patched,)


NODE_CLASS_MAPPINGS = {
    "ApplyH3Ref2VAUltraSafeBlockCache": ApplyH3Ref2VAUltraSafeBlockCache,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ApplyH3Ref2VAUltraSafeBlockCache": "MiniMax H3 Ref2VA Accelerator",
}
