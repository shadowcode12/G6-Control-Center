from app.backend.performance import PerformanceController


def test_profile_aliases_are_stable():
    controller = PerformanceController()

    assert controller.PROFILE_ALIASES["silent"] == "power-saver"
    assert controller.PROFILE_ALIASES["balanced"] == "balanced"
    assert controller.PROFILE_ALIASES["performance"] == "performance"
    assert controller.PROFILE_ALIASES["gaming"] == "performance"
