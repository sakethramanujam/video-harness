"""Worker process infrastructure for video processing and visual extraction.

Provides:
- True macOS physical footprint monitoring using Mach task info (task_info).
- Metal cache and memory caps.
- Background worker runner and job status management.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from video_harness.paths import config_dir


def get_macos_phys_footprint_bytes() -> int:
    """Read physical memory footprint (phys_footprint) in bytes via Mach task info on macOS.

    Returns 0 on non-macOS or if Mach API call fails.
    """
    if not sys.platform.startswith("darwin"):
        return 0

    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        mach_task_self = libc.mach_task_self
        mach_task_self.restype = ctypes.c_uint32

        # struct task_vm_info { ... mach_vm_size_t phys_footprint; ... }
        # TASK_VM_INFO = 22
        # TASK_VM_INFO_COUNT = sizeof(task_vm_info) / 4
        # We define a minimal buffer matching task_vm_info struct
        TASK_VM_INFO = 22
        # task_vm_info is ~176-200 bytes on 64-bit macOS
        vm_info_buf = (ctypes.c_uint32 * 64)()
        buf_size = ctypes.c_uint32(len(vm_info_buf))

        ret = libc.task_info(
            mach_task_self(),
            TASK_VM_INFO,
            ctypes.byref(vm_info_buf),
            ctypes.byref(buf_size),
        )
        if ret != 0:
            return 0

        # In 64-bit Darwin task_vm_info, phys_footprint is uint64 at offset 120 (uint32 index 30)
        # Verify via ctypes cast
        raw_bytes = bytes(vm_info_buf)
        # Offset for phys_footprint is 120 bytes in struct task_vm_info
        if len(raw_bytes) >= 128:
            import struct
            phys_footprint = struct.unpack_from("<Q", raw_bytes, 120)[0]
            return int(phys_footprint)
    except Exception:
        pass
    return 0


def configure_metal_memory_bounds(max_memory_gb: int = 8, max_cache_gb: int = 4) -> None:
    """Configure MLX / Metal memory limits if mlx is installed."""
    try:
        import mlx.core as mx  # type: ignore

        limit_bytes = max_memory_gb * 1024 * 1024 * 1024
        cache_bytes = max_cache_gb * 1024 * 1024 * 1024

        if hasattr(mx.metal, "set_memory_limit"):
            mx.metal.set_memory_limit(limit_bytes)
        if hasattr(mx.metal, "set_cache_limit"):
            mx.metal.set_cache_limit(cache_bytes)
    except ImportError:
        pass


class JobManager:
    """Tracks background video description jobs."""

    def __init__(self, jobs_dir: Path | None = None) -> None:
        self.jobs_dir = jobs_dir or (config_dir() / "jobs")
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _job_file(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def create_job(self, job_id: str, media_id: str, total_duration: float = 0.0) -> None:
        data = {
            "job_id": job_id,
            "media_id": media_id,
            "status": "running",
            "progress": 0.0,
            "created_at": time.time(),
            "updated_at": time.time(),
            "segments_count": 0,
            "memory_footprint_mb": 0.0,
            "error": None,
        }
        with open(self._job_file(job_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def update_progress(
        self,
        job_id: str,
        progress: float,
        segments_count: int = 0,
        footprint_bytes: int = 0,
    ) -> None:
        path = self._job_file(job_id)
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["progress"] = min(1.0, max(0.0, progress))
            data["segments_count"] = segments_count
            data["updated_at"] = time.time()
            if footprint_bytes > 0:
                data["memory_footprint_mb"] = round(footprint_bytes / (1024 * 1024), 2)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def finish_job(self, job_id: str, segments_count: int = 0, error: str | None = None) -> None:
        path = self._job_file(job_id)
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["status"] = "error" if error else "done"
            data["progress"] = 1.0 if not error else data.get("progress", 0.0)
            data["segments_count"] = segments_count
            data["updated_at"] = time.time()
            data["error"] = error
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        path = self._job_file(job_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
