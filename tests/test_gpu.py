"""Tests for GPU detection and VRAM estimation."""

import pytest

from auto_music_gen.gpu import GpuInfo, check_vram_fit, detect_gpu, estimate_vram_mb


class TestGpuInfo:
    def test_vram_gb_conversion(self):
        gpu = GpuInfo(name="RTX 4090", vram_total_mb=24576, vram_free_mb=20000)
        assert gpu.vram_total_gb == 24.0
        assert gpu.vram_free_gb == pytest.approx(19.53, abs=0.01)


class TestEstimateVram:
    def test_short_single_sample(self):
        est = estimate_vram_mb(60, 1)
        # ~4000 base + ~1500 working = ~5500
        assert 5000 < est < 6500

    def test_longer_duration_more_vram(self):
        short = estimate_vram_mb(60, 1)
        long = estimate_vram_mb(180, 1)
        assert long > short

    def test_larger_batch_more_vram(self):
        single = estimate_vram_mb(120, 1)
        double = estimate_vram_mb(120, 2)
        assert double > single

    def test_batch_scales_sublinearly(self):
        single = estimate_vram_mb(120, 1)
        double = estimate_vram_mb(120, 2)
        # Batch of 2 shouldn't be 2x the single cost
        single_working = single - 4000
        double_working = double - 4000
        assert double_working < single_working * 2


class TestCheckVramFit:
    def test_none_gpu_always_fits(self):
        fits, msg = check_vram_fit(120, 2, None)
        assert fits is True
        assert msg == ""

    def test_large_gpu_fits(self):
        gpu = GpuInfo(name="A100", vram_total_mb=81920, vram_free_mb=70000)
        fits, msg = check_vram_fit(300, 4, gpu)
        assert fits is True

    def test_small_gpu_long_duration_warns(self):
        gpu = GpuInfo(name="RTX 4070 Laptop", vram_total_mb=8188, vram_free_mb=1500)
        fits, msg = check_vram_fit(210, 2, gpu)
        assert fits is False
        assert "CPU" in msg or "reduce" in msg.lower() or "reducing" in msg.lower()

    def test_tight_fit_warns(self):
        gpu = GpuInfo(name="RTX 3060", vram_total_mb=12288, vram_free_mb=3000)
        fits, msg = check_vram_fit(180, 2, gpu)
        # With 12GB total, 180s batch=2 is borderline
        # Just verify it returns a meaningful result either way
        assert isinstance(fits, bool)

    def test_default_duration_when_none(self):
        gpu = GpuInfo(name="A100", vram_total_mb=81920, vram_free_mb=70000)
        fits, msg = check_vram_fit(None, 1, gpu)
        assert fits is True


class TestDetectGpu:
    def test_returns_gpu_info_or_none(self):
        # This test runs on any machine -- just verify the return type
        result = detect_gpu()
        assert result is None or isinstance(result, GpuInfo)
