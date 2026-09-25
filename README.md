# SageQL

SageQL is a Python package for building reports step by step. The current flow starts with the user's report question, asks for clarification when needed, prints its understanding, and resolves the request's context. It does not connect to a database or create a report yet.

## Run from `main.py`

Python 3.10 or newer is required. In PowerShell, from this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[openai]"
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\python.exe main.py
```

Put your API key in the `LLM_API_KEY` field of `.env`, or leave it blank and enter it at the hidden prompt. The example already contains the tested AvalAI Base URL and `gpt-5-nano` model. Fill in database fields if you know them; blank fields are requested interactively. `.env` is ignored by Git, and existing shell environment variables take precedence over the file. The OpenAI extra and API key are unnecessary for offline tests or a custom provider.

## Start a report conversation

The main file asks for your report question first, then uses the configuration from `.env` and prompts for missing fields. You can also run the installed CLI directly if you set environment variables yourself:

```powershell
sageql chat
```

The CLI first asks what report you want. It then collects these fields:

| Database | LLM |
| --- | --- |
| Server / Host | API Key |
| Database | Base URL |
| Authentication method | Model |
| ODBC Driver | |

If the request is unclear, answer the AI's clarification question at `You>`. Once understood, the program prints `Request understanding:` and resolves five context fields: time period, entities, metrics, filters, and comparison period. It asks another focused question if a material context detail is missing, then prints `Resolved context:` and stops. A time period is required; “all available data” is a valid answer. Empty optional filters and comparison periods print as `Not specified`. Relative phrases such as “last quarter” are preserved, not converted to exact dates. Type `/exit` to stop early. Without environment overrides, the Base URL defaults to `https://api.openai.com/v1` and the model to `gpt-5-nano`. A custom Base URL receives your API key, so use an endpoint you trust.

For the tested AvalAI configuration, set the non-secret defaults and let the CLI ask for the key privately:

```powershell
$env:LLM_BASE_URL = "https://api.avalai.ir/v1"
$env:LLM_MODEL = "gpt-5-nano"
sageql chat
```

## Python API

```python
import os

from sageql import (
    ChatConfig,
    ContextResolutionSession,
    DatabaseConfig,
    LLMConfig,
    RequestUnderstandingSession,
)
from sageql.chat_provider import OpenAIChatProvider

database = DatabaseConfig(
    server_host="db.example.com",
    database="sales",
    authentication="Windows",
    odbc_driver="ODBC Driver 18 for SQL Server",
)
llm = LLMConfig(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url="https://api.openai.com/v1",
    model="gpt-5-nano",
)
config = ChatConfig(database=database, llm=llm)
provider = OpenAIChatProvider(llm)
conversation = RequestUnderstandingSession(config, provider)
assessment = conversation.submit("I want a monthly sales report")
while not assessment.enough_information:
    print(assessment.clarification_question)
    assessment = conversation.submit(input("You> "))
print("Request understanding:", assessment.request_understanding)

context_session = ContextResolutionSession(
    config, provider, conversation.history, assessment.request_understanding
)
resolution = context_session.start()
while not resolution.ready:
    print(resolution.clarification_question)
    resolution = context_session.submit(input("You> "))
print("Resolved context:", resolution.context)
```

`conversation.history` contains successful user and assistant turns. You can inject another object with `assess(messages)` and `resolve_context(messages, understanding)` methods to use a different provider or test offline.

## Current scope and privacy

- Conversation messages and their request understanding go to the configured LLM endpoint. The Database configuration is held locally and is not sent to the LLM in this step.
- Context fields are the model's interpretation of the request. They are not yet checked against database tables, columns, or data; review them before later steps.
- The API key is hidden at the CLI prompt and masked in `LLMConfig` representations. SageQL keeps chat history in memory only; it does not save it.
- Authentication means the method name only. No database password or connection is used in this step.
- The earlier experimental SQLite SQL proposal command is still available as `sageql "question" --schema schema.sql`, but it is separate from the report conversation.

## Development

Read [`agent-rules/Agent.md`](agent-rules/Agent.md) for the AI development workflow and [`docs/ROADMAP.md`](docs/ROADMAP.md) for the implementation slices.

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m build
```
