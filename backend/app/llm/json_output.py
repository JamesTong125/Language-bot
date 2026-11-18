"""Turning model text into validated data, with one retry on bad output.

Providers differ in structured-output support, so the app never depends on it. Prompts ask
for JSON, and this module strips code fences, parses, and validates with Pydantic.
"""

import json
import logging
import re
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from app.llm.base import LLMOutputInvalidError, Message, SchemaT

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)

TextCompleter = Callable[[list[Message]], Awaitable[str]]


def strip_code_fences(text: str) -> str:
    """Remove a surrounding ```json ... ``` fence and any text outside the outer JSON value."""
    text = text.strip()
    match = _FENCE.match(text)
    if match:
        text = match.group(1).strip()
    # Small models sometimes add a sentence before or after the JSON object.
    if not text.startswith(("{", "[")):
        start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
        if start >= 0:
            text = text[start:]
    if text.startswith("{") and not text.endswith("}"):
        text = text[: text.rfind("}") + 1] or text
    elif text.startswith("[") and not text.endswith("]"):
        text = text[: text.rfind("]") + 1] or text
    return text


def parse_output(text: str, schema: type[SchemaT]) -> SchemaT:
    """Parse and validate. Raises ValueError (bad JSON) or ValidationError (bad shape)."""
    data = json.loads(strip_code_fences(text))
    return schema.model_validate(data)


def _describe_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        problems = [
            f"{'.'.join(str(p) for p in err['loc']) or '(root)'}: {err['msg']}"
            for err in exc.errors()[:5]
        ]
        return "; ".join(problems)
    return f"Not valid JSON ({exc})"


async def complete_json_with_retry(
    complete_text: TextCompleter, messages: list[Message], schema: type[SchemaT]
) -> SchemaT:
    """Ask once; on invalid output, ask once more with the validation error included."""
    first = await complete_text(messages)
    try:
        return parse_output(first, schema)
    except (ValueError, ValidationError) as exc:
        problem = _describe_error(exc)
        logger.info("LLM JSON output invalid, retrying once: %s", problem)

    retry_messages: list[Message] = [
        *messages,
        {"role": "assistant", "content": first},
        {
            "role": "user",
            "content": (
                f"Your reply was not valid. Problem: {problem}. "
                "Reply again with only the corrected JSON, no other text."
            ),
        },
    ]
    second = await complete_text(retry_messages)
    try:
        return parse_output(second, schema)
    except (ValueError, ValidationError) as exc:
        logger.warning("LLM JSON output invalid after retry: %s", _describe_error(exc))
        raise LLMOutputInvalidError(_describe_error(exc)) from exc
