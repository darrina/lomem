from dataclasses import asdict, dataclass

from .validation import RunInputs


@dataclass(frozen=True)
class EngineResult:
    primary_score: float
    confidence: float
    delta_from_baseline: float
    summary: str
    flags: list[str]
    explainability: dict[str, float]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def execute_validation(
    inputs: RunInputs,
    scenario: dict,
) -> EngineResult:
    baseline = float(scenario["baseline_score"])
    sensitivity = float(scenario["sensitivity"])

    normalized_signal = (inputs.signal_strength - inputs.noise_level) / 100.0
    load_factor = 1 - (inputs.memory_load / 200.0)
    bias_factor = 1 + (inputs.adaptation_bias * 0.25)

    raw_score = baseline + (normalized_signal * 0.35 * sensitivity)
    primary_score = _clamp(raw_score * load_factor * bias_factor, 0.0, 1.0)
    confidence = _clamp(
        0.55 + abs(normalized_signal) * 0.3 + (0.15 if inputs.memory_load < 70 else -0.1),
        0.0,
        1.0,
    )
    delta = primary_score - baseline

    flags: list[str] = []
    if inputs.noise_level > inputs.signal_strength:
        flags.append("Noise dominates signal.")
    if inputs.memory_load > 85:
        flags.append("High memory load dampens system responsiveness.")
    if abs(inputs.adaptation_bias) > 0.8:
        flags.append("Adaptation bias is near boundary conditions.")
    if not flags:
        flags.append("No risk flags triggered.")

    summary = (
        f"Scenario {scenario['name']} produced score {primary_score:.3f} "
        f"(delta {delta:+.3f} vs baseline)."
    )

    return EngineResult(
        primary_score=round(primary_score, 6),
        confidence=round(confidence, 6),
        delta_from_baseline=round(delta, 6),
        summary=summary,
        flags=flags,
        explainability={
            "baseline_score": round(baseline, 6),
            "normalized_signal": round(normalized_signal, 6),
            "load_factor": round(load_factor, 6),
            "bias_factor": round(bias_factor, 6),
            "sensitivity": round(sensitivity, 6),
        },
    )


def to_dict(result: EngineResult) -> dict:
    return asdict(result)
