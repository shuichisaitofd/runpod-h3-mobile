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
        global_threshold=0.110,
        video_threshold=0.110,
        audio_threshold=0.095,
        visual_ref_threshold=0.080,
        audio_ref_threshold=0.080,
        temporal_threshold=0.135,
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
    global_change: float = math.inf
    video_change: float = math.inf
    audio_change: float = math.inf
    visual_ref_change: float = math.inf
    audio_ref_change: float = math.inf
    temporal_change: float = math.inf


@dataclass
class CacheContext:
    previous_sigma: float | None = None
    previous_block0: torch.Tensor | None = None
    cached_tail_residual: torch.Tensor | None = None
    cached_tail_residual_cpu: torch.Tensor | None = None
    input_signature: tuple | None = None
    layout: Any = None
    has_refs: bool = False
    use_cache: bool = False
    metrics: StepMetrics = field(default_factory=StepMetrics)
    tail_scales: torch.Tensor | None = None
    hit_streak: int = 0

    def clear_tensors(self):
        self.previous_block0 = None
        self.cached_tail_residual = None
        self.cached_tail_residual_cpu = None
        self.tail_scales = None
        self.hit_streak = 0


def _safe_mean_abs(tensor: torch.Tensor | None) -> float:
    if tensor is None or not torch.is_tensor(tensor) or tensor.numel() == 0:
        return math.inf
    return float(tensor.detach().float().abs().mean().item())


def _relative_change(current: torch.Tensor | None, previous: torch.Tensor | None) -> float:
    if current is None or previous is None:
        return math.inf
    if not torch.is_tensor(current) or not torch.is_tensor(previous):
        return math.inf
    if tuple(current.shape) != tuple(previous.shape):
        return math.inf
    cur = current.detach().float()
    prev = previous.detach().float()
    denom = prev.abs().mean().clamp_min(1e-6)
    return float((cur - prev).abs().mean().div(denom).item())


def _temporal_change(tensor: torch.Tensor | None, layout) -> float:
    if tensor is None or layout is None or not torch.is_tensor(tensor):
        return math.inf
    try:
        target = layout.target_video
        start = int(target.start)
        end = int(target.end)
    except Exception:
        return math.inf
    if end <= start or tensor.ndim < 3:
        return math.inf
    sliced = tensor[:, start:end]
    if sliced.shape[1] < 2:
        return 0.0
    diffs = sliced[:, 1:] - sliced[:, :-1]
    denom = sliced[:, :-1].detach().float().abs().mean().clamp_min(1e-6)
    return float(diffs.detach().float().abs().mean().div(denom).item())


def _segment_change(current: torch.Tensor, previous: torch.Tensor, segment) -> float:
    try:
        start = int(segment.start)
        end = int(segment.end)
    except Exception:
        return math.inf
    if end <= start:
        return 0.0
    return _relative_change(current[:, start:end], previous[:, start:end])


class Ref2VABlockCacheRuntime:
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
        self.start_sigma = start_sigma
        self.end_sigma = end_sigma
        self.block_count = block_count
        self.storage = storage
        self.debug = debug
        self.block_modules = block_modules
        self.block_ids = tuple(id(block) for block in block_modules)
        self.tail_rescale = tail_rescale
        self.cpu_tail_compute = cpu_tail_compute
        self.contexts: dict[tuple[str, ...], CacheContext] = {}
        self.current: CacheContext | None = None
        self.prefetch_queue = None
        self._lock = threading.Lock()
        self.total_calls = 0
        self.full_steps = 0
        self.cache_hits = 0
        self.cache_misses = 0
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

    def decide_after_block0(self, block0_output: torch.Tensor):
        context = self.current
        if context is None:
            return
        self.total_calls += 1
        previous = context.previous_block0
        context.metrics.global_change = _relative_change(block0_output, previous)
        if previous is not None and context.layout is not None:
            try:
                context.metrics.video_change = _segment_change(block0_output, previous, context.layout.target_video)
                context.metrics.audio_change = _segment_change(block0_output, previous, context.layout.target_audio)
                visual_refs = list(getattr(context.layout, "visual_refs", []) or [])
                audio_refs = list(getattr(context.layout, "audio_refs", []) or [])
                if visual_refs:
                    context.metrics.visual_ref_change = max(_segment_change(block0_output, previous, seg) for seg in visual_refs)
                else:
                    context.metrics.visual_ref_change = 0.0
                if audio_refs:
                    context.metrics.audio_ref_change = max(_segment_change(block0_output, previous, seg) for seg in audio_refs)
                else:
                    context.metrics.audio_ref_change = 0.0
            except Exception:
                if not self._layout_warned:
                    logging.warning("[H3 Ref2VA Block Cache] Failed to read Ref2VA layout; cache disabled until layout is valid.")
                    self._layout_warned = True
        context.metrics.temporal_change = _temporal_change(block0_output, context.layout)

        cache_ready = context.cached_tail_residual is not None or context.cached_tail_residual_cpu is not None
        metrics_ok = (
            context.metrics.global_change <= self.config.global_threshold
            and context.metrics.video_change <= self.config.video_threshold
            and context.metrics.audio_change <= self.config.audio_threshold
            and context.metrics.visual_ref_change <= self.config.visual_ref_threshold
            and context.metrics.audio_ref_change <= self.config.audio_ref_threshold
            and context.metrics.temporal_change <= self.config.temporal_threshold
        )
        context.use_cache = bool(
            cache_ready
            and context.has_refs
            and self._within_window(context)
            and metrics_ok
            and context.hit_streak < self.config.max_consecutive_hits
            and not self.config.observe_only
        )
        if context.use_cache:
            self.cache_hits += 1
            context.hit_streak += 1
            if self.prefetch_queue is not None:
                try:
                    self.prefetch_queue.clear()
                    self.prefetch_suppressed_steps += 1
                except Exception:
                    pass
        else:
            self.cache_misses += 1
            context.hit_streak = 0
        context.previous_block0 = block0_output.detach().clone()

    def cached_tail_for(self, reference: torch.Tensor):
        context = self.current
        if context is None:
            return None
        if context.cached_tail_residual is not None:
            return context.cached_tail_residual.to(device=reference.device, dtype=reference.dtype, non_blocking=True)
        if context.cached_tail_residual_cpu is not None:
            return context.cached_tail_residual_cpu.to(device=reference.device, dtype=reference.dtype, non_blocking=True)
        return None

    def finish_full_step(self, output: torch.Tensor):
        context = self.current
        if context is None or context.previous_block0 is None:
            raise RuntimeError("H3 Ref2VA Block Cache full-step state is incomplete")
        residual = (output - context.previous_block0).detach()
        if self.tail_rescale:
            base = context.previous_block0.detach().float()
            tail = residual.float()
            denom = tail.flatten(2).norm(dim=2, keepdim=True).clamp_min(1e-6)
            target = base.flatten(2).norm(dim=2, keepdim=True).clamp_min(1e-6)
            scales = (target / denom).clamp(0.5, 2.0)
            context.tail_scales = scales
        else:
            context.tail_scales = None
        if self.storage == GPU_STORAGE:
            context.cached_tail_residual = residual
            context.cached_tail_residual_cpu = None
            self.gpu_tail_steps += 1
        else:
            context.cached_tail_residual = None
            context.cached_tail_residual_cpu = residual.to("cpu", non_blocking=False)
        self.full_steps += 1

    def maybe_rescale_tail(self, tail: torch.Tensor):
        context = self.current
        if context is None or context.tail_scales is None:
            return tail
        try:
            shape = tail.shape
            flat = tail.flatten(2)
            scales = context.tail_scales.to(device=tail.device, dtype=flat.dtype)
            return (flat * scales).reshape(shape)
        except Exception:
            return tail

    def summary(self, label: str) -> str:
        return (
            f"[H3 Ref2VA Block Cache {NODE_VERSION}] {label} | calls={self.total_calls} "
            f"full={self.full_steps} hits={self.cache_hits} misses={self.cache_misses} "
            f"prefetch_suppressed={self.prefetch_suppressed_steps} no_refs={self.steps_without_refs} "
            f"gpu_tail_steps={self.gpu_tail_steps}"
        )

    def reset(self):
        with self._lock:
            self.contexts.clear()
            self.current = None
            self.prefetch_queue = None


def make_block_patch(runtime: Ref2VABlockCacheRuntime, index: int, last_index: int):
    def patch(args, extra_options):
        # ComfyUI H3 block replacement calls receive a dict-like args payload. Keep support for
        # tuple/list variants to avoid binding the node to one minor ComfyUI implementation detail.
        if isinstance(args, dict):
            hidden_states = args.get("hidden_states")
            encoder_hidden_states = args.get("encoder_hidden_states")
            temb = args.get("temb")
            audio_hidden_states = args.get("audio_hidden_states")
            rotary_pos_emb = args.get("rotary_pos_emb")
            transformer_options = args.get("transformer_options", {})
            image_rotary_emb = args.get("image_rotary_emb")
            audio_rotary_emb = args.get("audio_rotary_emb")
            minimax_payload = args.get("minimax_payload")
        else:
            values = list(args)
            hidden_states = values[0] if len(values) > 0 else None
            encoder_hidden_states = values[1] if len(values) > 1 else None
            temb = values[2] if len(values) > 2 else None
            audio_hidden_states = values[3] if len(values) > 3 else None
            rotary_pos_emb = values[4] if len(values) > 4 else None
            transformer_options = values[5] if len(values) > 5 else {}
            image_rotary_emb = values[6] if len(values) > 6 else None
            audio_rotary_emb = values[7] if len(values) > 7 else None
            minimax_payload = values[8] if len(values) > 8 else None

        original_block = runtime.block_modules[index]
        output = original_block(
            hidden_states,
            encoder_hidden_states,
            temb,
            audio_hidden_states,
            rotary_pos_emb,
            transformer_options,
            image_rotary_emb=image_rotary_emb,
            audio_rotary_emb=audio_rotary_emb,
            minimax_payload=minimax_payload,
        )

        if isinstance(output, tuple):
            new_hidden = output[0]
            rest = output[1:]
        else:
            new_hidden = output
            rest = ()

        if index == 0:
            runtime.decide_after_block0(new_hidden)
            if runtime.current is not None and runtime.current.use_cache:
                cached_tail = runtime.cached_tail_for(new_hidden)
                if cached_tail is not None:
                    cached_tail = runtime.maybe_rescale_tail(cached_tail)
                    new_hidden = new_hidden + cached_tail
                    if rest:
                        return (new_hidden, *rest)
                    return new_hidden
        elif runtime.current is not None and runtime.current.use_cache:
            if rest:
                return (new_hidden, *rest)
            return new_hidden

        if index == last_index:
            runtime.finish_full_step(new_hidden)
        if rest:
            return (new_hidden, *rest)
        return new_hidden

    return patch


def make_diffusion_wrapper(runtime: Ref2VABlockCacheRuntime):
    def wrapper(executor, *args, **kwargs):
        x = args[0] if len(args) > 0 else kwargs.get("x")
        timestep = args[1] if len(args) > 1 else kwargs.get("timestep")
        transformer_options = kwargs.get("transformer_options")
        if transformer_options is None and len(args) > 3:
            transformer_options = args[3]
        transformer_options = transformer_options or {}
        minimax_payload = kwargs.get("minimax_payload")
        runtime.begin_call(x, timestep, transformer_options, minimax_payload=minimax_payload)
        try:
            return executor(*args, **kwargs)
        finally:
            runtime.end_call()

    return wrapper


def make_sample_wrapper(runtime: Ref2VABlockCacheRuntime, label: str):
    def wrapper(executor, *args, **kwargs):
        if not _PREFETCH_AVAILABLE:
            logging.warning(
                "[H3 Ref2VA Block Cache] comfy.model_prefetch unavailable; continuing without "
                "tail-prefetch suppression. Cache hits still skip block compute, but offloaded "
                "checkpoints may see reduced wall-clock savings."
            )
            try:
                return executor(*args, **kwargs)
            finally:
                logging.info("\n%s", runtime.summary(label))
                runtime.reset()

        original_make = comfy.model_prefetch.make_prefetch_queue

        def hooked_make(queue, device, transformer_options):
            return runtime.capture_prefetch_queue(original_make, queue, device, transformer_options)

        comfy.model_prefetch.make_prefetch_queue = hooked_make
        try:
            return executor(*args, **kwargs)
        finally:
            comfy.model_prefetch.make_prefetch_queue = original_make
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
        elif cache_storage == CPU_STORAGE:
            label = f"{label}; cpu_tail=Safe CPU"
        else:
            label = f"{label}; cache=GPU"

        patched = model.clone()
        diffusion_model = patched.get_model_object("diffusion_model")
        if not hasattr(diffusion_model, "blocks"):
            raise RuntimeError("MiniMax H3 diffusion model does not expose .blocks")
        block_count = len(diffusion_model.blocks)
        if block_count < 2:
            raise RuntimeError(f"Unexpected MiniMax H3 block count: {block_count}")

        # Existing block replacement patches are not composable with this cache: the cache owns the
        # whole H3 block chain so that cache-hit steps can skip blocks 1..N deterministically.
        object_patches = getattr(patched, "object_patches", {}) or {}
        for key in object_patches:
            key_text = str(key).lower()
            if "blocks_replace" in key_text or "double_block" in key_text:
                raise RuntimeError(
                    "H3 Ref2VA Block Cache cannot be stacked after another H3 block-replacement patch "
                    "(for example Spectrum). Remove the other block replacement on this branch."
                )

        start_sigma = max(0.0, 1.0 - config.start_percent)
        end_sigma = max(0.0, 1.0 - config.end_percent)
        runtime = Ref2VABlockCacheRuntime(
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
