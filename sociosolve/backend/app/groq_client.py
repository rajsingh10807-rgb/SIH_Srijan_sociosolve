"""
Groq chat-completion client with automatic key rotation.

The active API key and model are stored in the database (see
`models.ApiKey` / `models.AppSetting`), not in environment variables, so
an admin can rotate an expired key from the hidden dashboard without
touching the server. As a safety net, if the currently-active key fails
with an authentication/quota error, this module automatically tries the
other keys on file (in the order they were added) and promotes the
first one that works — so a single expired key doesn't take the whole
platform down between the moment it dies and the moment a human notices.
"""
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from . import models
from app.config import settings

CHAT_ENDPOINT = f"{settings.GROQ_BASE_URL}/chat/completions"
REQUEST_TIMEOUT_SECONDS = 30

SYSTEM_PROMPT = (
    "You are the AI assistant embedded in SocioSolve, a civic platform where "
    "citizens post real-world societal problems (water, health, agriculture, "
    "energy, education, environment, infrastructure) and students/experts "
    "propose solutions. Given a problem, write a concise, practical, and "
    "actionable first-response: a short diagnosis of the issue, 2-4 concrete "
    "next steps or solution directions, and, if relevant, who should be "
    "involved (e.g. local municipal body, NGO, students of a given "
    "discipline). Keep it under 200 words, use plain language, and avoid "
    "restating the question back verbatim."
)


class AIServiceError(Exception):
    """Raised when no working Groq key is available."""

def get_active_model(db: Session) -> str:
    row = db.query(models.AppSetting).filter(
        models.AppSetting.key == "active_model"
    ).first()
    return str(row.value) if row else settings.DEFAULT_GROQ_MODEL


def set_active_model(db: Session, model_name: str) -> None:
    row = db.query(models.AppSetting).filter(models.AppSetting.key == "active_model").first()
    if row:
        row.value= model_name
    else:
        row = models.AppSetting(key="active_model", value=model_name)
        db.add(row)
    db.commit()


def _ordered_candidate_keys(db: Session) -> list[models.ApiKey]:
    """Active key first, then the rest by insertion order, so a fallback
    always prefers the key the admin explicitly marked active."""
    active = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.provider == "groq", models.ApiKey.is_active.is_(True))
        .all()
    )
    others = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.provider == "groq", models.ApiKey.is_active.is_(False))
        .order_by(models.ApiKey.added_at.asc())
        .all()
    )
    return active + others


def _call_groq(api_key: str, model: str, user_prompt: str) -> str:
    response = requests.post(
        CHAT_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 400,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise requests.HTTPError(
            f"{response.status_code}: {response.text[:300]}", response=response
        )
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _promote(db: Session, key_row: models.ApiKey) -> None:
    db.query(models.ApiKey).filter(models.ApiKey.provider == "groq").update({"is_active": False})
    key_row.is_active = True
    db.commit()


def generate_ai_answer(db: Session, title: str, description: str, category: str) -> str:
    """Generate an AI answer for a question, trying every stored Groq key
    until one works. Raises AIServiceError if none do (or none exist)."""
    candidates = _ordered_candidate_keys(db)
    if not candidates:
        raise AIServiceError(
            "No Groq API key is configured yet. Ask an admin to add one from the dashboard."
        )

    model = get_active_model(db)
    user_prompt = (
        f"Problem category: {category}\nTitle: {title}\nDescription: {description}\n\n"
        "Provide your response now."
    )

    last_error_message = "Unknown error."
    for key_row in candidates:
        try:
            answer_text = _call_groq(key_row.key_value, model, user_prompt)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            key_row.last_error = str(exc)
            key_row.last_error_at = datetime.utcnow()
            db.commit()
            last_error_message = str(exc)

            if status_code == 400:
                # A malformed request (e.g. an invalid/decommissioned model
                # name) fails identically no matter which key sends it —
                # cycling through every key would just waste quota, so
                # surface this immediately instead.
                raise AIServiceError(
                    f"Groq rejected the request (400): {exc}. This is usually an invalid "
                    "model name — check it from the hidden dashboard."
                )
            # 401/403/429 (bad, expired, or rate-limited key) and 5xx
            # (transient Groq-side issue) are both worth retrying with the
            # next key on file.
            continue
        except requests.RequestException as exc:
            key_row.last_error = f"Network error: {exc}"
            key_row.last_error_at = datetime.utcnow()
            db.commit()
            last_error_message = str(exc)
            continue
        else:
            # Success — record usage and make sure this is the active key
            # so future requests go straight to a known-good one.
            key_row.last_used_at = datetime.utcnow()
            key_row.last_error = None
            key_row.last_error_at = None
            if not key_row.is_active:
                _promote(db, key_row)
            else:
                db.commit()
            return answer_text

    raise AIServiceError(
        "All configured Groq API keys failed (likely expired or rate-limited). "
        f"Last error: {last_error_message} — an admin needs to add a fresh key "
        "from the hidden dashboard."
    )


def test_key(api_key: str, model: str) -> tuple[bool, str]:
    """Used by the admin dashboard's 'Test key' button. Returns
    (ok, message)."""
    try:
        text = _call_groq(api_key, model, "Reply with the single word: OK")
        return True, text[:120]
    except requests.HTTPError as exc:
        return False, str(exc)
    except requests.RequestException as exc:
        return False, f"Network error: {exc}"
