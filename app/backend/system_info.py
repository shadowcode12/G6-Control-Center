from __future__ import annotations

from pathlib import Path
import platform

import psutil


def get_cpu_usage() -> float:
    return psutil.cpu_percent(interval=0.05)


def get_cpu_frequency() -> float | None:
    try:
        value = psutil.cpu_freq()
        return float(value.current) if value else None
    except (AttributeError, OSError):
        return None


def get_ram_usage() -> tuple[float, float, float]:
    memory = psutil.virtual_memory()
    used_gb = memory.used / (1024 ** 3)
    total_gb = memory.total / (1024 ** 3)
    return memory.percent, used_gb, total_gb


def get_cpu_temperature() -> float | None:
    try:
        sensors = psutil.sensors_temperatures()

        for name in ("coretemp", "k10temp", "zenpower"):
            if name in sensors and sensors[name]:
                return sensors[name][0].current

        for entries in sensors.values():
            if entries:
                return entries[0].current
    except (AttributeError, OSError):
        pass

    return None


def get_system_info() -> dict:
    product = Path("/sys/class/dmi/id/product_name")
    vendor = Path("/sys/class/dmi/id/sys_vendor")

    return {
        "model": product.read_text(encoding="utf-8").strip()
        if product.exists()
        else "Unknown",
        "vendor": vendor.read_text(encoding="utf-8").strip()
        if vendor.exists()
        else "Unknown",
        "kernel": platform.release(),
        "platform": platform.platform(),
    }
