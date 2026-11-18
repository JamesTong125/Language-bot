"""Builds the message lists sent to the LLM. Pure functions, unit tested."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.languages import LANGUAGES
from app.llm.base import Message
from app.prompts import render_prompt

PARTNER_PROMPT = "partner_reply_v1"
OPENING_PROMPT = "partner_opening_v1"
HINT_PROMPT = "hint_v1"
ANALYSIS_PROMPT = "analysis_v1"
WRAPUP_PROMPT = "wrapup_v1"

_LANGUAGE_NAMES = {lang.code: lang.name for lang in LANGUAGES}

_LENGTH_RULES = {
    "A1": "1 to 3 short sentences.",
    "A2": "1 to 3 short sentences.",
    "B1": "2 to 4 sentences.",
    "B2": "up to 5 sentences.",
    "C1": "up to 5 sentences.",
    "C2": "up to 5 sentences.",
}

_LEVEL_RULES = {
    "A1": "Use the present tense, everyday words, and very short, simple sentences.",
    "A2": "Use simple present and past tenses and common everyday words.",
    "B1": "Use common tenses and familiar topics. Avoid idioms and rare words.",
    "B2": "Use natural, varied language. Explain an idiom if you use one.",
    "C1": "Speak naturally, as you would to a fluent adult.",
    "C2": "Speak naturally and idiomatically, as you would to a native speaker.",
}


@dataclass(frozen=True)
class SceneContext:
    title: str
    description: str
    persona: str
    goal: str
    target_language: str  # ISO code
    native_language: str  # ISO code
    level: str  # CEFR


@dataclass(frozen=True)
class TurnText:
    role: str  # "learner" or "partner"
    text: str


def language_name(code: str) -> str:
    return _LANGUAGE_NAMES.get(code, code)


def partner_system_prompt(scene: SceneContext) -> str:
    """Static for a whole session, so provider-side prompt caching can apply."""
    return render_prompt(
        PARTNER_PROMPT,
        target_language=language_name(scene.target_language),
        native_language=language_name(scene.native_language),
        level=scene.level,
        length_rule=_LENGTH_RULES[scene.level],
        level_rule=_LEVEL_RULES[scene.level],
        title=scene.title,
        description=scene.description,
        persona=scene.persona,
        goal=scene.goal,
    )


def _history(turns: Sequence[TurnText], limit: int) -> list[Message]:
    recent = list(turns)[-limit:] if limit > 0 else []
    return [
        {"role": "assistant" if t.role == "partner" else "user", "content": t.text} for t in recent
    ]


def build_partner_messages(
    scene: SceneContext, turns: Sequence[TurnText], history_limit: int = 20
) -> list[Message]:
    """System prompt, then the last ``history_limit`` turns.

    Chat APIs expect the first non-system message to come from the user. The partner
    speaks first in every scene, so the opening cue always leads the history.
    """
    messages: list[Message] = [{"role": "system", "content": partner_system_prompt(scene)}]
    history = _history(turns, history_limit)
    if not history or history[0]["role"] == "assistant":
        messages.append({"role": "user", "content": render_prompt(OPENING_PROMPT)})
    messages.extend(history)
    return messages


@dataclass(frozen=True)
class AnalysisInput:
    target_language: str  # ISO code
    native_language: str  # ISO code
    level: str  # CEFR
    learner_text: str
    previous_partner_text: str | None
    scene: str = ""  # e.g. "Job interview, talking to a hiring manager." Sets the register.


def build_analysis_messages(item: AnalysisInput) -> list[Message]:
    """Static rules in the system prompt; the message to check in a separate user message."""
    system = render_prompt(
        ANALYSIS_PROMPT,
        target_language=language_name(item.target_language),
        native_language=language_name(item.native_language),
        level=item.level,
    )
    context = f"SCENE: {item.scene}\n" if item.scene else ""
    if item.previous_partner_text:
        context += f"PARTNER SAID (context only, don't check): {item.previous_partner_text}\n"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{context}LEARNER MESSAGE: {item.learner_text}"},
    ]


@dataclass(frozen=True)
class CorrectionText:
    original: str
    corrected: str
    error_type: str


WRAPUP_MAX_TURNS = 40
WRAPUP_MAX_CORRECTIONS = 30


def build_wrapup_messages(
    scene: SceneContext,
    turns: Sequence[TurnText],
    corrections: Sequence[CorrectionText],
    max_vocab: int,
) -> list[Message]:
    """Corrections are numbered C1, C2, ... so the model can say which one a word came from.

    Callers must pass at most WRAPUP_MAX_CORRECTIONS corrections, in the same order they
    will resolve "Cn" ids against.
    """
    assert len(corrections) <= WRAPUP_MAX_CORRECTIONS
    system = render_prompt(
        WRAPUP_PROMPT,
        target_language=language_name(scene.target_language),
        native_language=language_name(scene.native_language),
        level=scene.level,
        max_vocab=str(max_vocab),
    )
    recent = list(turns)[-WRAPUP_MAX_TURNS:]
    transcript = "\n".join(
        f"{'PARTNER' if t.role == 'partner' else 'LEARNER'}: {t.text}" for t in recent
    )
    listed = "\n".join(
        f"C{i}: {c.original} -> {c.corrected} ({c.error_type})"
        for i, c in enumerate(corrections, start=1)
    )
    body = (
        f"SCENE: {scene.title}\n\nCONVERSATION:\n{transcript}\n\nCORRECTIONS:\n{listed or '(none)'}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": body}]


def build_hint_messages(
    scene: SceneContext, turns: Sequence[TurnText], history_limit: int = 20
) -> list[Message]:
    system = render_prompt(
        HINT_PROMPT,
        target_language=language_name(scene.target_language),
        level=scene.level,
        title=scene.title,
        persona=scene.persona,
        goal=scene.goal,
    )
    recent = list(turns)[-history_limit:]
    lines = [f"{'PARTNER' if t.role == 'partner' else 'LEARNER'}: {t.text}" for t in recent]
    transcript = "\n".join(lines) or "(The conversation has not started yet.)"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"CONVERSATION SO FAR:\n{transcript}"},
    ]
