# Showcase site

A static page of example conversations, published at
<https://sinaqp.github.io/SageQL/>. Each example shows what the model received,
what it returned, the SQL that SageQL compiled with the user's row policy, and the
reply. All data is invented ([host.py](host.py)).

## How the data is made

[build.py](build.py) runs every conversation in [examples_spec.py](examples_spec.py)
through the real engine on synthetic SQLite data and writes `site/showcase.json`.
Only the model's replies are replayed; validation, policy, SQL compilation and
execution happen on every build.

- **Recorded examples** replay the replies saved in `recording.json`.
- **Scripted examples** use placeholder replies from `examples_spec.py` until a
  recording exists. The site labels them.
- **Simulated attacks** always use hand-written hostile replies, to show what the
  engine does when a model is wrong or compromised. The site labels them.

Every model input is checked for the host's table names, column names and
policy values (`HIDDEN_FROM_MODEL` in host.py); the result is shown on the page.
[tests/test_showcase.py](../../tests/test_showcase.py) rebuilds the data offline
and fails if it no longer matches the committed `showcase.json`.

## Commands

```bash
python examples/showcase/build.py            # offline rebuild from recording.json
python examples/showcase/build.py --record   # one live run, then commit recording.json and site/
python -m http.server 8790 --directory examples/showcase/site   # preview locally
```

`--record` reads `LLM_API_KEY`, `LLM_BASE_URL` and `LLM_MODEL` (the planner model)
from `.env`, uses `gpt-5-mini` for intent like the recommended host setup, and
makes about 16 model calls in total (roughly $0.05). If any call fails it saves
nothing, so it can simply be run again. Re-record after SDK changes that alter the
model calls; the test says when.
