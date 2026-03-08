#!/usr/bin/env python3
from __future__ import annotations

import os
import platform
import sys


def _print_header() -> None:
    print("python:", sys.executable)
    print("python_version:", sys.version.split()[0])
    print("platform:", platform.platform())


def _print_torch_section() -> bool:
    try:
        import torch
    except Exception as exc:
        print("\n[torch] import failed:", repr(exc))
        return False

    print("\n[torch]")
    print("torch_version:", torch.__version__)
    print("torch_cuda_available:", torch.cuda.is_available())
    print("torch_cuda_version_build:", torch.version.cuda)
    print("torch_cudnn_version:", torch.backends.cudnn.version())
    if not torch.cuda.is_available():
        return False

    index = 0
    props = torch.cuda.get_device_properties(index)
    print("cuda_device_count:", torch.cuda.device_count())
    print("cuda_device_0_name:", torch.cuda.get_device_name(index))
    print("cuda_device_0_capability:", torch.cuda.get_device_capability(index))
    print("cuda_device_0_total_mem_GB:", round(props.total_memory / (1024**3), 2))
    return True


def _print_env_section() -> None:
    print("\n[env]")
    for name in ("CUDA_PATH", "CUDA_HOME", "CUDA_VISIBLE_DEVICES"):
        print(f"{name}:", os.environ.get(name))


def _print_torchvision_section() -> bool:
    try:
        import torchvision
        from torchvision.ops import nms  # noqa: F401
    except Exception as exc:
        print("\n[torchvision] import/ops failed:", repr(exc))
        return False

    print("\n[torchvision]")
    print("torchvision_version:", torchvision.__version__)
    print("torchvision_ops_nms_import: ok")
    return True


def main() -> int:
    _print_header()
    cuda_ready = _print_torch_section()
    _print_env_section()
    torchvision_ready = _print_torchvision_section()
    return 0 if (cuda_ready and torchvision_ready) else 1


if __name__ == "__main__":
    raise SystemExit(main())
