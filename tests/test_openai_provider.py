from types import SimpleNamespace

import pytest

from sageql import GenerationError
from sageql.openai_provider import OpenAIProvider


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.output_text)


def test_openai_provider_requests_structured_output():
    responses = FakeResponses('{"sql":"SELECT 1","explanation":"Constant"}')
    provider = OpenAIProvider(model="test-model", client=SimpleNamespace(responses=responses))

    result = provider.generate("one", "CREATE TABLE t(id INT)")

    assert result.sql == "SELECT 1"
    assert result.explanation == "Constant"
    assert responses.kwargs["model"] == "test-model"
    assert responses.kwargs["text"]["format"]["type"] == "json_schema"
    assert "CREATE TABLE t(id INT)" in responses.kwargs["input"]


@pytest.mark.parametrize("response", ["not-json", '{"sql": 1, "explanation": "x"}', "[]"])
def test_openai_provider_rejects_bad_response(response):
    provider = OpenAIProvider(client=SimpleNamespace(responses=FakeResponses(response)))
    with pytest.raises(GenerationError):
        provider.generate("one", "schema")
