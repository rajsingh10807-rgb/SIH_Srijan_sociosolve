# SocioSolve

A civic Q&A platform: citizens post real-world problems, other users answer
them, and any logged-in user can request an instant **AI Insight** powered
by Groq's free-tier LLM API. A **hidden admin dashboard** lets you rotate
the Groq API key (or swap the model) the moment one expires or gets
rate-limited — no redeploy required.

Backend: **FastAPI** + SQLAlchemy + SQLite. Frontend: plain HTML/CSS/JS
served by the same FastAPI app (no build step, no framework).

---

## 1. How it fits together

```
sociosolve/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, static hosting, startup seeding
│   │   ├── config.py          All settings, read from environment / .env
│   │   ├── database.py        SQLAlchemy engine/session
│   │   ├── models.py          User, Question, Answer, ApiKey, AppSetting
│   │   ├── schemas.py         Pydantic request/response models
│   │   ├── security.py        Password hashing (PBKDF2) + JWT
│   │   ├── deps.py            get_current_user / get_current_admin
│   │   ├── groq_client.py     Calls Groq, auto-fails-over across keys
│   │   └── routers/
│   │       ├── auth_router.py     /api/auth/signup, /login, /me
│   │       ├── questions.py       /api/questions/...  (ask, browse, answer, AI insight)
│   │       └── admin.py           /api/admin/...      (keys, model, stats — admin only)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                  Public site — signup, browse, ask, answer
│   ├── index.html / styles.css / app.js
└── admin_frontend/            Hidden dashboard — NOT linked from frontend/
    ├── index.html / admin.css / admin.js
```

Everything is served by one FastAPI process:
- `/api/*` → the backend routers above
- `/*` → `frontend/` (the public site)
- **`ADMIN_PATH`** (from `.env`, default `/console-7f2a1d`) → `admin_frontend/`

`admin_frontend/` lives as a **sibling** of `frontend/`, not a subfolder of
it — if it were nested inside `frontend/`, it would still be reachable at
the predictable `/admin` path once the public site is mounted, which
would defeat the whole point of "hidden."

## 2. Getting a free Groq API key

1. Create an account at [console.groq.com](https://console.groq.com/keys).
2. Generate an API key (starts with `gsk_...`). Groq's free tier is
   generous and needs no credit card at the time of writing — check
   their current limits on that page, since rate limits and available
   models do change.

You can either drop this key into `.env` as `GROQ_API_KEY` so it's seeded
automatically on first run, or add it later from the admin dashboard —
either way works, and once it's in the database you manage it from the
dashboard.

## 3. Setup

Requires **Python 3.10+** (the code uses the `str | None` union syntax).

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env:
#   - set JWT_SECRET to a long random string
#   - set ADMIN_PATH to something only you know
#   - set ADMIN_USERNAME / ADMIN_PASSWORD (bootstrap admin account)
#   - set GROQ_API_KEY (optional but recommended for first run)

uvicorn app.main:app --reload --port 8000
```

Open:
- **Public site** → http://127.0.0.1:8000/
- **Admin dashboard** → http://127.0.0.1:8000&lt;ADMIN_PATH&gt; (e.g.
  `http://127.0.0.1:8000/console-7f2a1d`), log in with the
  `ADMIN_USERNAME` / `ADMIN_PASSWORD` you set in `.env`.
- **API docs** (Swagger) → http://127.0.0.1:8000/docs — handy for testing
  endpoints directly.

The SQLite database file (`sociosolve.db`) is created automatically in
the `backend/` folder the first time you run the app; tables and the
bootstrap admin/key are created in a `startup` hook, so there's no
separate migration step for this project's scope.

## 4. How users work

There's a single account type — anyone can sign up, ask a question, and
answer other people's questions. Signup can never create an admin
account; admin accounts only come from `ADMIN_USERNAME`/`ADMIN_PASSWORD`
in `.env` on first boot (or by manually flipping `is_admin` in the
database). This is intentional: it keeps the hidden dashboard reachable
only by someone who already controls the server's environment, not by
anyone who registers through the public signup form.

## 5. How the AI Insight feature works

On a question page, any logged-in user can click **Get AI Insight**. That
calls `POST /api/questions/{id}/ai-answer`, which:

1. Loads the currently active Groq key + model from the database.
2. Sends the question to Groq's OpenAI-compatible chat-completions
   endpoint with a system prompt tuned for short, practical civic-problem
   responses.
3. Saves the reply as a normal answer, tagged `is_ai_generated = true`
   (shown in the UI as an "AI Insight" badge instead of a username).

If the active key fails with an auth or rate-limit error, `groq_client.py`
automatically tries every other key on file (oldest first) and — the
moment one works — promotes it to "active" so the next request goes
straight to a known-good key. If *every* key fails, the user sees a clear
"AI is temporarily unavailable" message instead of a crash, and the
failure (with the underlying error) is recorded against each key so an
admin can see exactly what happened.

## 6. Rotating a key from the dashboard

1. Go to `ADMIN_PATH`, sign in.
2. Under **Groq API keys** you'll see every key on file, which one is
   active, when it was last used, and its last error (if any) — an
   expired key will show something like `401: Invalid API Key` after the
   first failed AI Insight request.
3. Paste a new key into **New key**, optionally label it (e.g. "backup —
   personal account"), leave **Make active** checked, and click **Add
   key**. The old one stays in the list (inactive) in case you need to
   fall back to it later, or you can delete it.
4. Use **Test** on any key to fire a tiny real request at Groq and
   confirm it works before relying on it.

No restart, no redeploy — the very next AI Insight request uses the new
key.

## 7. Security notes (read before deploying for real)

This was built to be genuinely usable, not just a demo, but a few things
are worth tightening for production use beyond a hackathon/judging
environment:

- **Set a real `JWT_SECRET`.** If you don't, the app generates a random
  one on every boot, which means everyone gets logged out on every
  restart. That's a safe default, not a convenient one.
- **Change `ADMIN_PATH` to something unguessable**, and treat it like a
  secret (don't commit it, don't put it in client-side code, don't share
  it in a support ticket). Hiding the path is *obscurity*, not
  authentication — the real protection is that `/api/admin/*` always
  checks `is_admin` server-side regardless of which URL reached it.
- **Serve over HTTPS in production** so the JWT and Groq key never
  travel in plaintext.
- **Password hashing** uses salted PBKDF2-SHA256 (260k iterations) from
  Python's standard library rather than bcrypt/argon2, specifically so
  this project has no compiled/native dependencies and installs cleanly
  everywhere. If you'd rather use argon2 or bcrypt, that's a self-
  contained change inside `security.py` only.
- **Lock down `CORS_ALLOW_ORIGINS`** in `.env` once the frontend has a
  real production domain, instead of leaving it at `*`.

## 8. Extending it

- Add categories: edit `CATEGORIES` in both `backend/app/schemas.py` and
  `frontend/app.js` (kept as plain lists on purpose, no shared config
  file, to keep the project dependency-free).
- Swap the AI provider: everything Groq-specific lives in
  `groq_client.py`; the rest of the app only calls
  `generate_ai_answer(db, title, description, category)`.
- Swap SQLite for Postgres: change `DATABASE_URL` in `.env` (e.g.
  `postgresql+psycopg2://user:pass@host/db`) and add `psycopg2-binary` to
  `requirements.txt` — nothing else in the code is SQLite-specific.
