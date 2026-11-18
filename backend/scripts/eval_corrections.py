"""Run the seeded correction cases against the real analysis model. Not part of the suite.

    docker compose exec api python -m scripts.eval_corrections [--runs N]

Uses the same prompt, validation, retry, and filtering as the app. Prints each case's result
and a pass rate. Learner messages in the cases are made up, so printing them is fine.
"""

import argparse
import asyncio
import logging

from app.conversation.prompt_builder import build_analysis_messages
from app.llm.base import LLMError
from app.llm.factory import get_analysis_llm
from app.schemas.analysis import AnalysisOut, usable_corrections
from tests.correction_cases import CorrectionCase, FoundCorrection, check_case, load_cases


async def run_case(
    case: CorrectionCase,
) -> tuple[list[str], list[FoundCorrection] | None, list[str]]:
    llm = get_analysis_llm()
    try:
        out = await llm.complete_json(
            build_analysis_messages(case.item), AnalysisOut, usage_tag="eval"
        )
    except LLMError as exc:
        return [f"analysis failed: {type(exc).__name__}"], None, []
    usable = usable_corrections(out, case.item.learner_text)
    found = [FoundCorrection(c.original, c.corrected, c.error_type) for c in usable]
    return check_case(case, found), found, [c.explanation for c in usable]


async def main(runs: int) -> None:
    logging.basicConfig(level=logging.WARNING)
    cases = load_cases()
    passed = total = 0
    for case in cases:
        for _ in range(runs):
            problems, found, explanations = await run_case(case)
            total += 1
            passed += not problems
            mark = "PASS" if not problems else "FAIL"
            print(f"{mark} {case.id}: {case.item.learner_text}")
            for f, why in zip(found or [], explanations, strict=True):
                print(f"       {f.original!r} -> {f.corrected!r} [{f.error_type}] {why}")
            for p in problems:
                print(f"       ! {p}")
    print(f"\n{passed}/{total} passed ({100 * passed // max(total, 1)}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, help="Runs per case")
    asyncio.run(main(parser.parse_args().runs))
