import pytest
from pydantic import ValidationError

from app.llm.base import LLMOutputInvalidError
from app.llm.json_output import parse_output, strip_code_fences
from app.schemas.conversation import HintOut
from tests.fakes import FakeLLMClient

GOOD = '{"suggestions": ["Quisiera un café, por favor.", "¿Cuánto cuesta?"]}'


@pytest.mark.parametrize(
    "raw",
    [
        GOOD,
        f"```json\n{GOOD}\n```",
        f"```\n{GOOD}\n```",
        f"  ```JSON\n{GOOD}```  ",
        f"Here you go:\n{GOOD}",
        f"{GOOD}\nHope this helps!",
    ],
)
def test_strip_code_fences_recovers_the_json(raw: str) -> None:
    assert strip_code_fences(raw) == GOOD


def test_parse_output_validates() -> None:
    assert parse_output(GOOD, HintOut).suggestions[1] == "¿Cuánto cuesta?"


def test_hint_validator_rejects_bad_shapes() -> None:
    for bad in (
        '{"suggestions": []}',
        '{"suggestions": ["  "]}',
        '{"hints": ["a"]}',
        '{"suggestions": ["a", "b", "c", "d"]}',
        '{"suggestions": ["' + "x" * 201 + '"]}',
    ):
        with pytest.raises(ValidationError):
            parse_output(bad, HintOut)


async def test_valid_output_needs_one_call() -> None:
    llm = FakeLLMClient([GOOD])
    result = await llm.complete_json([{"role": "user", "content": "hi"}], HintOut)
    assert len(result.suggestions) == 2
    assert len(llm.calls) == 1


async def test_malformed_json_is_retried_once_with_the_error() -> None:
    llm = FakeLLMClient(['{"suggestions": ["unclosed"', GOOD])
    result = await llm.complete_json([{"role": "user", "content": "hi"}], HintOut)
    assert result.suggestions[0] == "Quisiera un café, por favor."
    retry = llm.calls[1]
    assert retry[-2] == {"role": "assistant", "content": '{"suggestions": ["unclosed"'}
    assert "Not valid JSON" in retry[-1]["content"]


async def test_schema_error_is_described_in_the_retry() -> None:
    llm = FakeLLMClient(['{"hints": ["a"]}', GOOD])
    await llm.complete_json([{"role": "user", "content": "hi"}], HintOut)
    assert "suggestions" in llm.calls[1][-1]["content"]


async def test_malformed_json_twice_raises_output_invalid() -> None:
    llm = FakeLLMClient(["not json at all", "still not json"])
    with pytest.raises(LLMOutputInvalidError):
        await llm.complete_json([{"role": "user", "content": "hi"}], HintOut)
    assert len(llm.calls) == 2
