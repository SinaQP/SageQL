"""OpenAI-compatible chat adapter for report-planning conversations."""

import json
from typing import Any, Sequence

from sageql.conversation import ChatError, LLMConfig, Message
from sageql.understanding import RequestAssessment


_INSTRUCTIONS = (
    "You are SageQL's report-planning assistant. Help the user clarify the "
    "report they want. Ask concise, relevant follow-up questions about the "
    "metrics, filters, time range, grouping, and desired output when needed. "
    "Do not claim to have connected to a database, inspected data, generated "
    "SQL, or created a report. This conversation is only the first step."
)

_UNDERSTANDING_INSTRUCTIONS = (
    "You assess what report the user wants. Decide whether the conversation "
    "contains enough information to describe the report's subject and intended "
    "result without inventing details. Ask for clarification only if an ambiguity "
    "would materially change the report. Do not require every optional formatting "
    "preference. If information is missing, ask exactly one focused question. "
    "If enough information is present, write a concise request understanding "
    "using only details the user supplied. Do not generate SQL, connect to a "
    "database, or create a report. Return only the requested JSON object."
)

_UNDERSTANDING_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "request_understanding",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "enough_information": {"type": "boolean"},
                "request_understanding": {"type": "string"},
                "clarification_question": {"type": "string"},
            },
            "required": [
                "enough_information",
                "request_understanding",
                "clarification_question",
            ],
            "additionalProperties": False,
        },
    },
}


class OpenAIChatProvider:
    """Use a configurable OpenAI-compatible Chat Completions endpoint."""

    def __init__(self, config: LLMConfig, client: Any = None) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ChatError(
                    "install the OpenAI extra: pip install 'sageql[openai]'"
                ) from exc
            try:
                client = OpenAI(api_key=config.api_key, base_url=config.base_url)
            except Exception as exc:
                raise ChatError("could not initialize the chat provider") from exc
        self._client = client
        self._model = config.model

    def reply(self, messages: Sequence[Message]) -> str:
        request_messages = [{"role": "system", "content": _INSTRUCTIONS}]
        request_messages.extend(
            {"role": message.role, "content": message.content} for message in messages
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=request_messages,
            )
            answer = response.choices[0].message.content
        except Exception as exc:
            raise ChatError("model request failed") from exc
        if not isinstance(answer, str) or not answer.strip():
            raise ChatError("model returned an empty answer")
        return answer

    def assess(self, messages: Sequence[Message]) -> RequestAssessment:
        request_messages = [{"role": "system", "content": _UNDERSTANDING_INSTRUCTIONS}]
        request_messages.extend(
            {"role": message.role, "content": message.content} for message in messages
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=request_messages,
                response_format=_UNDERSTANDING_FORMAT,
            )
            content = response.choices[0].message.content
        except Exception as exc:
            raise ChatError("model assessment request failed") from exc

        try:
            result = json.loads(content)
            expected = {
                "enough_information",
                "request_understanding",
                "clarification_question",
            }
            if not isinstance(result, dict) or set(result) != expected:
                raise ValueError("unexpected assessment fields")
            return RequestAssessment(**result)
        except (TypeError, ValueError) as exc:
            raise ChatError("model returned an invalid request assessment") from exc
