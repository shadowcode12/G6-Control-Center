from app.backend.battery import BatteryController
from app.backend.fans import FanController
from app.backend.graphics import GraphicsController
from app.backend.intel_gpu import IntelGpuController
from app.backend.keyboard import KeyboardController
from app.backend.nvidia import NvidiaController
from app.backend.performance import PerformanceController


def test_profile_aliases():
    assert PerformanceController.PROFILE_ALIASES == {
        "silent": "power-saver",
        "balanced": "balanced",
        "performance": "performance",
        "gaming": "performance",
    }


def test_epp_values_are_constrained():
    assert set(PerformanceController.EPP_OPTIONS) == {
        "performance",
        "balance_performance",
        "balance_power",
        "power",
    }


def test_native_backends_construct_without_hardware_writes():
    PerformanceController()
    NvidiaController()
    IntelGpuController()
    GraphicsController()
    FanController()
    BatteryController()
    KeyboardController()


def test_native_keyboard_backend_does_not_call_third_party_tools():
    keyboard = KeyboardController()
    result = keyboard.keyboard_status()
    assert not result.ok
    assert "gigactl" in result.stderr
