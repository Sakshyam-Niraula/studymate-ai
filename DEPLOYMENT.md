# StudyMate AI deployment notes

## Required environment variables

Configure these values in the hosting provider's environment settings:

- `FLASK_SECRET_KEY`: a long, random secret used to sign Flask sessions. Keep it stable between deploys. Generate one locally with `python -c "import secrets; print(secrets.token_hex(32))"`.
- `GEMINI_API_KEY`: the API key for the Gemini project.
- `GEMINI_MODEL`: primary model available to that Gemini project.
- `GEMINI_FALLBACK_MODEL`: a second model available to that Gemini project.
- `FLASK_DEBUG`: keep this set to `false` in production.

The model names in `.env.example` are defaults, not a guarantee that every Gemini project has access to them. If the API reports a model-not-found error, set the two model variables to model IDs that are available in the project's Gemini API model list.

## Render

Use this start command if the service does not already have one:

```bash
gunicorn --workers 1 --threads 4 --timeout 120 Studymate:app
```

Add the environment variables above in the Render service dashboard. Do not put secrets in source code, commits, screenshots, or public issue reports.

## Beta storage note

Study materials, feedback and the active quiz are currently stored in the app's local `uploads/` directory. This is suitable for the current temporary beta workflow, but local files on a typical Render web service are ephemeral and can disappear after a restart or redeploy. Do not promise long-term document or feedback retention until persistent storage or a database is added.

## Student Beta limits

The current per-session limits are intentionally unchanged:

- 5 successful AI tutor questions
- 1 successfully generated quiz

These counters are stored in the signed Flask session. They are session-level beta controls, not account-based quotas.

## Tests

Run the regression suite with:

```bash
python -m unittest discover -s tests -v
```
