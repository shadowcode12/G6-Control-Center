import subprocess


def get_gpu_info() -> dict:
    command = [
        "nvidia-smi",
        "--query-gpu=name,temperature.gpu,utilization.gpu,"
        "power.draw,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )

        values = [value.strip() for value in result.stdout.strip().split(",")]

        if len(values) < 6:
            return {"available": False}

        return {
            "available": True,
            "name": values[0],
            "temperature": float(values[1]),
            "usage": float(values[2]),
            "power": float(values[3]),
            "memory_used": float(values[4]),
            "memory_total": float(values[5]),
        }

    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        return {"available": False}