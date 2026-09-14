"""
Central configuration for the SocioSolve backend.

Every value can be overridden with an environment variable (or a `.env`
file next to this project — see `.env.example`). Nothing sensitive is
hard-coded: the Groq API key in particular is NOT read from here at
request time, it lives in the database so it can be rotated from the
hidden admin dashboard without restarting the server.
"""
import os
import secrets

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # --- General ---
    APP_NAME: str = "SocioSolve"
    ENV: str = os.getenv("ENV", "development")

    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sociosolve.db")

    # --- Auth / JWT ---
    # In production ALWAYS set JWT_SECRET yourself. We generate a random
    # one on boot as a safety net so the app never runs with a known
    # default secret, but that also means tokens stop working across
    # restarts unless you pin it in your .env.
    JWT_SECRET: str = os.getenv("JWT_SECRET") or secrets.token_hex(32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days

    # --- Hidden admin dashboard ---
    # This is the *only* place this path is defined. The frontend has no
    # link pointing at it. Change it in your .env to something only you
    # know, e.g. ADMIN_PATH=/ops-9f2c7a
    ADMIN_PATH: str = os.getenv("ADMIN_PATH", "/console-7f2a1d")

    # Optional bootstrap admin account, created once on first startup if
    # no admin user exists yet and these are set.
    ADMIN_USERNAME: str | None = os.getenv("ADMIN_USERNAME")
    ADMIN_EMAIL: str | None = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD: str | None = os.getenv("ADMIN_PASSWORD")

    # Optional: seed the very first Groq key from the environment so the
    # app works immediately after `docker run` / `uvicorn` without a
    # manual dashboard visit. Once it's in the database you manage
    # rotations from the dashboard instead of this variable.
    GROQ_API_KEY_BOOTSTRAP: str | None = os.getenv("GROQ_API_KEY")

    # --- Groq ---
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    DEFAULT_GROQ_MODEL: str = os.getenv("DEFAULT_GROQ_MODEL", "openai/gpt-oss-20b")

    # --- CORS ---
    # "*" is fine for local dev / hackathon demos. Lock this down to your
    # real frontend origin(s) in production.
    CORS_ALLOW_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
    ]


settings = Settings()
