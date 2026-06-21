"""Tự động chọn GPU (NVIDIA CUDA) hoặc CPU cho Faster Whisper.

Faster Whisper chạy trên CTranslate2, không dùng PyTorch.
Kiểm tra CUDA qua ctranslate2.get_cuda_device_count() là chính xác nhất.

Ví dụ khi bạn viết transcriber:

    from utils.device import load_whisper_model, format_device_summary

    model, config = load_whisper_model("base", download_root="models")
    print(format_device_summary(config))  # hiển thị trên UI
    segments, info = model.transcribe("video.mp4", language="zh")
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

DeviceType = Literal["cuda", "cpu"]
ComputeType = Literal["float16", "int8_float16", "int8", "float32"]


@dataclass(frozen=True)
class WhisperDeviceConfig:
    device: DeviceType
    compute_type: ComputeType
    using_gpu: bool
    cuda_device_count: int
    gpu_name: str | None
    reason: str


def get_cuda_device_count():
    try:
        import ctranslate2

        count = ctranslate2.get_cuda_device_count()

        # Test thực sự xem CUDA runtime có hoạt động không
        from ctypes import CDLL
        CDLL("cublas64_12.dll")

        return int(count)

    except Exception:
        return 0


def _get_gpu_name() -> str | None:
    """Lấy tên GPU NVIDIA qua nvidia-smi (nếu có). Không bắt buộc."""
    import shutil
    import subprocess

    if not shutil.which("nvidia-smi"):
        return None

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0].strip()
    except Exception:
        pass
    return None


def detect_whisper_config(prefer_gpu: bool = True) -> WhisperDeviceConfig:
    """Chọn device + compute_type tối ưu cho máy hiện tại."""
    cuda_count = get_cuda_device_count()

    if prefer_gpu and cuda_count > 0:
        return WhisperDeviceConfig(
            device="cuda",
            compute_type="float16",
            using_gpu=True,
            cuda_device_count=cuda_count,
            gpu_name=_get_gpu_name(),
            reason="NVIDIA CUDA khả dụng — dùng GPU để tăng tốc STT",
        )

    if cuda_count > 0 and not prefer_gpu:
        reason = "Người dùng chọn chế độ CPU"
    elif cuda_count == 0:
        reason = "Không phát hiện GPU NVIDIA / CUDA — dùng CPU"
    else:
        reason = "Dùng CPU"

    return WhisperDeviceConfig(
        device="cpu",
        compute_type="int8",
        using_gpu=False,
        cuda_device_count=cuda_count,
        gpu_name=None,
        reason=reason,
    )


def format_device_summary(config: WhisperDeviceConfig) -> str:
    """Chuỗi ngắn gọn để hiển thị trên UI."""
    if config.using_gpu:
        name = config.gpu_name or "NVIDIA GPU"
        return f"GPU: {name} ({config.compute_type})"
    if config.cuda_device_count > 0:
        return f"CPU ({config.compute_type}) — có GPU nhưng đang tắt"
    return f"CPU ({config.compute_type}) — máy không có GPU NVIDIA"


def load_whisper_model(
    model_size: str,
    *,
    download_root: str | None = None,
    prefer_gpu: bool = True,
    cpu_threads: int | None = None,
):
    """Tải WhisperModel: thử GPU trước, tự fallback CPU nếu lỗi.

    Returns:
        (model, config) — config phản ánh device thực tế đang dùng.
    """
    from faster_whisper import WhisperModel

    config = detect_whisper_config(prefer_gpu=prefer_gpu)
    model = _try_load_model(
        WhisperModel,
        model_size,
        config,
        download_root=download_root,
        cpu_threads=cpu_threads,
    )
    if model is not None:
        return model, config

    if config.device != "cuda":
        raise RuntimeError("Không thể tải model Faster Whisper trên CPU")

    cpu_config = WhisperDeviceConfig(
        device="cpu",
        compute_type="int8",
        using_gpu=False,
        cuda_device_count=config.cuda_device_count,
        gpu_name=None,
        reason="GPU lỗi khi tải model — tự động chuyển sang CPU",
    )
    model = _try_load_model(
        WhisperModel,
        model_size,
        cpu_config,
        download_root=download_root,
        cpu_threads=cpu_threads,
    )
    if model is None:
        raise RuntimeError("Không thể tải model Faster Whisper (GPU và CPU đều thất bại)")

    return model, cpu_config


def _try_load_model(
    whisper_model_cls,
    model_size: str,
    config: WhisperDeviceConfig,
    *,
    download_root: str | None,
    cpu_threads: int | None,
):
    kwargs: dict = {
        "model_size_or_path": model_size,
        "device": config.device,
        "compute_type": config.compute_type,
    }
    if download_root:
        kwargs["download_root"] = download_root
    if config.device == "cpu":
        kwargs["cpu_threads"] = cpu_threads or max(1, (os.cpu_count() or 4) // 2)

    try:
        return whisper_model_cls(**kwargs)
    except Exception:
        return None
