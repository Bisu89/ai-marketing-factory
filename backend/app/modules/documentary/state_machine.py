"""Pure workflow rules for a documentary project -- no DB, no I/O, so the
backend enforces them identically from every caller.

The happy path is one linear chain. A transition into state T is allowed
only if (a) T is the next state in the chain and (b) every approval gate
whose review state lies *before* T is currently valid (approved, against the
current artifact version). That single rule is what keeps expensive work
(asset generation, TTS, render) behind its gate.
"""

from __future__ import annotations

from app.core.exceptions import ValidationError

# Linear happy path. "failed" is off-chain (see fail/resume in service).
STATES: tuple[str, ...] = (
    "draft",
    "research_review",
    "script_review",
    "storyboard_review",
    "asset_generation",
    "asset_review",
    "audio_ready",
    "render_preview",
    "final_review",
    "approved",
    "exported",
)
FAILED = "failed"
ALL_STATES = STATES + (FAILED,)

# gate -> (state in which it can be approved, artifact version column)
GATES: dict[str, tuple[str, str]] = {
    "research": ("research_review", "research_version"),
    "script": ("script_review", "script_version"),
    "storyboard_assets": ("asset_review", "storyboard_version"),
    "narration_timing": ("audio_ready", "narration_version"),
    "final": ("final_review", "render_version"),
}
GATE_ORDER: tuple[str, ...] = tuple(GATES)

# artifact kind -> the gate that approves it
ARTIFACT_GATE: dict[str, str] = {
    "research": "research",
    "script": "script",
    "storyboard": "storyboard_assets",
    "narration": "narration_timing",
    "render": "final",
}


def state_index(state: str) -> int:
    try:
        return STATES.index(state)
    except ValueError:
        raise ValidationError(f"Trạng thái không hợp lệ: {state!r}") from None


def gate_state(gate: str) -> str:
    if gate not in GATES:
        raise ValidationError(f"Cổng duyệt không tồn tại: {gate!r}")
    return GATES[gate][0]


def required_gates(target: str) -> list[str]:
    """Gates that must be valid before a project may enter `target`."""
    t = state_index(target)
    return [g for g in GATE_ORDER if state_index(GATES[g][0]) < t]


def gates_invalidated_by_rewind(to_state: str) -> list[str]:
    """Rewinding to `to_state` re-opens that stage, so every gate reviewed
    in it or later must be re-approved."""
    t = state_index(to_state)
    return [g for g in GATE_ORDER if state_index(GATES[g][0]) >= t]


def gates_invalidated_by_artifact(artifact: str) -> list[str]:
    if artifact not in ARTIFACT_GATE:
        raise ValidationError(f"Loại artifact không hợp lệ: {artifact!r}")
    start = GATE_ORDER.index(ARTIFACT_GATE[artifact])
    return list(GATE_ORDER[start:])


def check_advance(current: str, valid_gates: set[str]) -> str:
    """Return the next state, or raise a Vietnamese ValidationError."""
    if current == FAILED:
        raise ValidationError("Dự án đang ở trạng thái lỗi — hãy tiếp tục (resume) trước.")
    i = state_index(current)
    if i + 1 >= len(STATES):
        raise ValidationError("Dự án đã ở trạng thái cuối cùng.")
    target = STATES[i + 1]
    missing = [g for g in required_gates(target) if g not in valid_gates]
    if missing:
        raise ValidationError(
            f"Chưa thể chuyển sang '{target}': cổng duyệt chưa được phê duyệt hoặc đã cũ: {', '.join(missing)}"
        )
    return target
