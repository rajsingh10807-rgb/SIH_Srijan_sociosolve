import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import models
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import admin, auth_router, questions
from .security import hash_password

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent  # project root
FRONTEND_DIR = BASE_DIR / "frontend"
# Deliberately a SIBLING of frontend/, not a subfolder of it — if it lived
# inside frontend/ it would still be reachable at the obvious /admin path
# once frontend/ is mounted at "/", defeating the point of hiding it.
ADMIN_FRONTEND_DIR = BASE_DIR / "admin_frontend"

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(questions.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # --- Seed an admin account, if configured and none exists yet ---
        admin_exists = db.query(models.User).filter(models.User.is_admin.is_(True)).first()
        if not admin_exists and settings.ADMIN_USERNAME and settings.ADMIN_PASSWORD:
            db.add(
                models.User(
                    username=settings.ADMIN_USERNAME,
                    email=settings.ADMIN_EMAIL or f"{settings.ADMIN_USERNAME}@sociosolve.local",
                    hashed_password=hash_password(settings.ADMIN_PASSWORD),
                    is_admin=True,
                )
            )
            db.commit()
            print(f"[startup] Created admin account '{settings.ADMIN_USERNAME}'.")

        # --- Seed a Groq key from the environment, if one was given and
        # none is stored yet. After this, rotate keys via the dashboard. ---
        has_any_key = db.query(models.ApiKey).first()
        if not has_any_key and settings.GROQ_API_KEY_BOOTSTRAP:
            db.add(
                models.ApiKey(
                    provider="groq",
                    label="bootstrap (from .env)",
                    key_value=settings.GROQ_API_KEY_BOOTSTRAP,
                    is_active=True,
                )
            )
            db.commit()
            print("[startup] Seeded initial Groq API key from GROQ_API_KEY env var.")
    finally:
        db.close()

    print(f"[startup] Hidden admin dashboard mounted at: {settings.ADMIN_PATH}")


# --- Static hosting -------------------------------------------------------
# Mounted *after* the API routers above so /api/* always wins. The admin
# UI is mounted at a path only whoever configured ADMIN_PATH knows about;
# the public frontend has no link to it anywhere.
if ADMIN_FRONTEND_DIR.exists():
    app.mount(
        settings.ADMIN_PATH,
        StaticFiles(directory=str(ADMIN_FRONTEND_DIR), html=True),
        name="admin-frontend",
    )

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
