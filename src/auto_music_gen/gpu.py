"""GPU detection and VRAM estimation utilities."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class GpuInfo:
    """Detected GPU information."""

    name: str
    vram_total_mb: int
    vram_free_mb: int

    @property
    def vram_total_gb(self) -> float:
        return self.vram_total_mb / 1024

    @property
    def vram_free_gb(self) -> float:
        return self.vram_free_mb / 1024


def detect_gpu() -> GpuInfo | None:
    """Detect GPU via nvidia-smi. Returns None if no GPU found."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            return None

        return GpuInfo(
            name=parts[0],
            vram_total_mb=int(parts[1]),
            vram_free_mb=int(parts[2]),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


# Rough VRAM estimates for ACE-Step inference (in MB).
# These are approximate -- actual usage depends on model variant and settings.
# Base model weights: ~3.5GB. VAE: ~0.5GB. Working memory scales with duration+batch.
_MODEL_BASE_MB = 4000  # DiT + VAE loaded


def estimate_vram_mb(duration_seconds: float, batch_size: int) -> int:
    """Estimate peak VRAM usage for a generation job.

    This is a rough heuristic based on observed usage patterns:
    - Base model weights: ~4GB
    - Working memory scales roughly linearly with duration and batch size
    - 60s/batch=1 needs ~1.5GB working memory
    - Each additional batch sample adds ~70% of the per-sample cost
    """
    per_sample_mb = 1500 * (duration_seconds / 60)
    batch_overhead = per_sample_mb + (batch_size - 1) * per_sample_mb * 0.7
    return int(_MODEL_BASE_MB + batch_overhead)


def check_vram_fit(
    duration_seconds: float | None, batch_size: int, gpu: GpuInfo | None
) -> tuple[bool, str]:
    """Check if a generation job will likely fit in VRAM.

    Returns:
        (fits, message) -- fits is True if OK, message explains the issue if not.
    """
    if gpu is None:
        return True, ""  # Can't check, assume OK

    dur = duration_seconds if duration_seconds else 120.0  # default ~2min
    estimated = estimate_vram_mb(dur, batch_size)
    total = gpu.vram_total_mb

    if estimated > total:
        return False, (
            f"Estimated VRAM: ~{estimated / 1024:.1f}GB "
            f"(GPU has {total / 1024:.1f}GB total). "
            f"This will likely fall back to CPU and take hours. "
            f"Try reducing duration or batch size."
        )

    headroom = total - estimated
    if headroom < 500:  # Less than 500MB free after estimate
        return False, (
            f"Estimated VRAM: ~{estimated / 1024:.1f}GB "
            f"(GPU has {total / 1024:.1f}GB total, {gpu.vram_free_mb}MB free). "
            f"Very tight -- may fall back to CPU. "
            f"Consider batch_size=1 or shorter duration."
        )

    return True, ""
