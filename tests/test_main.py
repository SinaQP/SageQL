from pathlib import Path

import main as app_main


def test_main_loads_local_env_without_overriding_shell(monkeypatch):
    calls = []
    monkeypatch.setattr(app_main, "load_dotenv", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(app_main, "chat_main", lambda: 0)

    assert app_main.main() == 0
    assert calls == [
        {
            "dotenv_path": Path(app_main.__file__).resolve().parent / ".env",
            "override": False,
        }
    ]
