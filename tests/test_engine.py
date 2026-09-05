from lomem.engine import execute_validation
from lomem.validation import RunInputs


def test_placeholder_engine_is_deterministic():
    scenario = {"name": "Alpha Stability", "baseline_score": 0.62, "sensitivity": 1.15}
    inputs = RunInputs(
        memory_load=40,
        signal_strength=70,
        noise_level=20,
        adaptation_bias=0.1,
    )

    first = execute_validation(inputs, scenario)
    second = execute_validation(inputs, scenario)

    assert first == second
