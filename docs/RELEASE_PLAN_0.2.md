# Release plan: SageQL 0.2.0

Goal: a version that works on real Rahtal data, is cheap to run, and installs
cleanly. Steps 1–2 need no money; steps 3–5 need about **$0.15** of AvalAI credit.

## 1. Offline housekeeping (Claude, $0)

- [ ] Bump version `0.1.0` → `0.2.0` in `pyproject.toml`.
- [ ] Write `CHANGELOG.md` (per-stage models, compiled intent, no reviewer call,
      report interpretation, saved reports, test levels, cleanup).
- [ ] Make the measured setup the SDK default (`compile_intent=True`,
      `review=False`, low reasoning effort) and update scripted tests.
- [ ] Build wheel + sdist, install in a fresh venv, run the offline examples
      (`examples/sdk_demo.py`, `examples/multi_domain.py`).
- [ ] Full offline suite green.

## 2. Release-blocker review (Claude, $0)

- [ ] Re-read README "Try it" and Rahtal commands; run them in demo mode.
- [ ] Check every doc link; remove stale statements.
- [ ] Check the web page in demo mode: chat, report, interpretation line, save,
      run saved, delete.

## 3. Live smoke test (you approve, ~$0.01)

```powershell
python -m evaluations.model_comparison --level smoke --output dist/eval/release-smoke --authorization-id "<you> <date> cap 0.05"
```

Pass: 4 of 5 turns correct, no wrong accepted report, no rate-limit errors.

## 4. Rahtal manual test (you run, ~$0.05)

Follow [RAHTAL_MANUAL_TEST.md](RAHTAL_MANUAL_TEST.md): 20 questions plus saving
one report and re-running it. Send back the score sheet (question number + what
was wrong).

Pass: at least 15/20 as expected, no wrong numbers on the SQL cross-checks, saved
report re-runs with the same numbers.

## 5. Fix and confirm (Claude, then ~$0.04–0.09)

- [ ] Turn each real failure into an offline regression test and fix it.
- [ ] Re-run `standard` (or `full` if the setup changed).

## 6. Release

- [ ] Merge to `main`, tag `v0.2.0`, push.
- [ ] Update README status and roadmap.

## Known limits shipped in 0.2.0

Native SQL Server behavior unverified (no approved test server), local token
instead of real user login, no share-of-total / absence / per-group top-N
operations, saved reports are personal only.
