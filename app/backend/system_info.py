import psutil


def get_cpu_usage() -> float:
    return psutil.cpu_percent(interval=0.1)


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

    except Exception:
        pass

    return None