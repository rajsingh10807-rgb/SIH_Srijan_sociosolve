from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import groq_client, models, schemas
from ..config import settings
from ..database import get_db
from ..deps import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _mask(key_value: str) -> str:
    if len(key_value) <= 10:
        return "*" * len(key_value)
    return f"{key_value[:6]}{'*' * (len(key_value) - 10)}{key_value[-4:]}"


def _to_key_out(k: models.ApiKey) -> schemas.ApiKeyOut:
    return schemas.ApiKeyOut(
        id=k.id,
        provider=k.provider,
        label=k.label,
        masked_key=_mask(k.key_value),
        is_active=k.is_active,
        added_at=k.added_at,
        last_used_at=k.last_used_at,
        last_error=k.last_error,
        last_error_at=k.last_error_at,
    )


@router.get("/stats", response_model=schemas.AdminStats)
def stats(db: Session = Depends(get_db), _admin: models.User = Depends(get_current_admin)):
    total_users = db.query(models.User).count()
    total_questions = db.query(models.Question).count()
    total_answers = db.query(models.Answer).count()
    ai_answers = db.query(models.Answer).filter(models.Answer.is_ai_generated.is_(True)).count()
    open_questions = db.query(models.Question).filter(models.Question.status == "open").count()
    active_key = db.query(models.ApiKey).filter(models.ApiKey.is_active.is_(True)).first()
    return schemas.AdminStats(
        total_users=total_users,
        total_questions=total_questions,
        total_answers=total_answers,
        ai_answers=ai_answers,
        open_questions=open_questions,
        active_key_present=active_key is not None,
        active_model=groq_client.get_active_model(db),
    )


@router.get("/keys", response_model=list[schemas.ApiKeyOut])
def list_keys(db: Session = Depends(get_db), _admin: models.User = Depends(get_current_admin)):
    keys = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.provider == "groq")
        .order_by(models.ApiKey.is_active.desc(), models.ApiKey.added_at.desc())
        .all()
    )
    return [_to_key_out(k) for k in keys]


@router.post("/keys", response_model=schemas.ApiKeyOut, status_code=status.HTTP_201_CREATED)
def add_key(
    payload: schemas.ApiKeyCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    key = models.ApiKey(provider="groq", label=payload.label, key_value=payload.key_value.strip())
    db.add(key)
    db.commit()
    db.refresh(key)

    if payload.make_active:
        db.query(models.ApiKey).filter(
            models.ApiKey.provider == "groq", models.ApiKey.id != key.id
        ).update({"is_active": False})
        key.is_active = True
        db.commit()
        db.refresh(key)

    return _to_key_out(key)


@router.post("/keys/{key_id}/activate", response_model=schemas.ApiKeyOut)
def activate_key(
    key_id: int, db: Session = Depends(get_db), _admin: models.User = Depends(get_current_admin)
):
    key = db.query(models.ApiKey).filter(models.ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found.")
    db.query(models.ApiKey).filter(models.ApiKey.provider == key.provider).update(
        {"is_active": False}
    )
    key.is_active = True
    db.commit()
    db.refresh(key)
    return _to_key_out(key)


@router.post("/keys/{key_id}/test")
def test_key(
    key_id: int, db: Session = Depends(get_db), _admin: models.User = Depends(get_current_admin)
):
    key = db.query(models.ApiKey).filter(models.ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found.")
    ok, message = groq_client.test_key(key.key_value, groq_client.get_active_model(db))
    return {"ok": ok, "message": message}


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_key(
    key_id: int, db: Session = Depends(get_db), _admin: models.User = Depends(get_current_admin)
):
    key = db.query(models.ApiKey).filter(models.ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found.")
    db.delete(key)
    db.commit()
    return None


@router.get("/settings", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db), _admin: models.User = Depends(get_current_admin)):
    return schemas.SettingsOut(active_model=groq_client.get_active_model(db))


@router.put("/settings", response_model=schemas.SettingsOut)
def update_settings(
    payload: schemas.SettingsUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    groq_client.set_active_model(db, payload.active_model)
    return schemas.SettingsOut(active_model=payload.active_model)


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _admin: models.User = Depends(get_current_admin)):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.get("/whoami")
def whoami(_admin: models.User = Depends(get_current_admin)):
    """Lets the dashboard's login screen confirm the logged-in account is
    actually an admin before showing anything sensitive."""
    return {"ok": True, "admin_path": settings.ADMIN_PATH}
