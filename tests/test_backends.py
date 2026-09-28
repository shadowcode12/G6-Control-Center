from app.backend.battery import BatteryController
from app.backend.gigactl import GigaCtlController
from app.backend.nvidia import NvidiaController
from app.backend.performance import PerformanceController

def test_profile_aliases():
    assert PerformanceController.PROFILE_ALIASES == {
        'silent': 'power-saver',
        'balanced': 'balanced',
        'performance': 'performance',
        'gaming': 'performance',
    }

def test_epp_values_are_constrained():
    assert set(PerformanceController.EPP_OPTIONS) == {
        'performance', 'balance_performance', 'balance_power', 'power'
    }

def test_invalid_keyboard_color_is_rejected():
    result = GigaCtlController().keyboard_color('not-a-color')
    assert not result.ok

def test_backends_construct_without_hardware_writes():
    PerformanceController()
    NvidiaController()
    BatteryController()
    GigaCtlController()