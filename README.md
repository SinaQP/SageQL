# SageQL

SageQL is a Python package for building reports step by step. The current step starts a conversation about the report the user wants and captures the configuration shown in the project diagram. It does not connect to a database or create a report yet.

## Install

Python 3.10 or newer is required. From this repository:

```powershell
python -m pip install -e ".[openai]"
```

The CLI asks for an API key without echoing it. You can set `LLM_API_KEY` (or `OPENAI_API_KEY`) instead. `LLM_BASE_URL` and `LLM_MODEL` set the defaults shown in the prompts. The OpenAI extra and API key are unnecessary for offline tests or a custom provider. Keep keys out of project files and source control.

## Start a report conversation

Run:

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

After the first AI reply, enter follow-up messages at `You>`. Type `/exit` to end the session. Without environment overrides, the Base URL defaults to `https://api.openai.com/v1` and the model to `gpt-6-astra`. A custom Base URL receives your API key, so use an endpoint you trust.

For the tested AvalAI configuration, set the non-secret defaults and let the CLI ask for the key privately:

```powershell
$env:LLM_BASE_URL = "https://api.avalai.ir/v1"
$env:LLM_MODEL = "gpt-5-nano"
sageql chat
```

## Python API

```python
import os

from sageql import ChatConfig, DatabaseConfig, LLMConfig, ReportConversation
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
    model="gpt-6-astra",
)
conversation = ReportConversation(
    ChatConfig(database=database, llm=llm), OpenAIChatProvider(llm)
)
print(conversation.ask("I want a monthly sales report"))
print(conversation.ask("Show revenue by region for the last year"))
```

`conversation.history` contains successful user and assistant turns. You can inject another object with a `reply(messages)` method to use a different provider or test offline.

## Current scope and privacy

- Conversation messages go to the configured LLM endpoint. The Database configuration is held locally and is not sent to the LLM in this step.
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
