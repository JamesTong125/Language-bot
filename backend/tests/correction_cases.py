"""Seeded learner messages with known mistakes, and how to check a result against them.

Used by the test suite (with a fake model) and by ``scripts.eval_corrections`` (with the
real analysis model).
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.conversation.prompt_builder import AnalysisInput

CASES_FILE = Path(__file__).parent / "data" / "correction_cases.json"


@dataclass(frozen=True)
class Expectation:
    original_contains: str
    corrected_contains: str | None = None
    error_type: str | None = None


@dataclass(frozen=True)
class CorrectionCase:
    id: str
    item: AnalysisInput
    expected: list[Expectation]


@dataclass(frozen=True)
class FoundCorrection:
    original: str
    corrected: str
    error_type: str


def load_cases(path: Path = CASES_FILE) -> list[CorrectionCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        CorrectionCase(
            id=c["id"],
            item=AnalysisInput(
                target_language=c["target_language"],
                native_language=c["native_language"],
                level=c["level"],
                learner_text=c["learner_text"],
                previous_partner_text=c.get("previous_partner_text"),
                scene=c.get("scene", ""),
            ),
            expected=[Expectation(**e) for e in c["expected"]],
        )
        for c in raw
    ]


def _matches(expect: Expectation, found: FoundCorrection) -> bool:
    if expect.original_contains.casefold() not in found.original.casefold():
        return False
    corrected_ok = expect.corrected_contains is None or (
        expect.corrected_contains.casefold() in found.corrected.casefold()
    )
    type_ok = expect.error_type is None or expect.error_type == found.error_type
    return corrected_ok and type_ok


def check_case(case: CorrectionCase, found: list[FoundCorrection]) -> list[str]:
    """Return problems; an empty list means the case passed.

    Every expected mistake must be found. A case that expects no mistakes must get none.
    Extra corrections on a case with mistakes are allowed: models often add a valid
    second fix, and the spans are already checked against the learner's text.
    """
    if not case.expected:
        return [f"expected no corrections, got {len(found)}"] if found else []
    return [
        f"missing: {e.original_contains!r} -> {e.corrected_contains!r} ({e.error_type})"
        for e in case.expected
        if not any(_matches(e, f) for f in found)
    ]
