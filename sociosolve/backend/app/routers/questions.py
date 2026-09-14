from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..groq_client import AIServiceError, generate_ai_answer

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _to_list_item(q: models.Question) -> schemas.QuestionListItem:
    return schemas.QuestionListItem(
        id=q.id,
        title=q.title,
        category=q.category,
        status=q.status,
        created_at=q.created_at,
        author_username=q.author.username,
        answer_count=len(q.answers),
    )


def _to_answer_out(a: models.Answer) -> schemas.AnswerOut:
    return schemas.AnswerOut(
        id=a.id,
        question_id=a.question_id,
        body=a.body,
        is_ai_generated=a.is_ai_generated,
        created_at=a.created_at,
        author_username=(a.author.username if a.author else ("AI" if a.is_ai_generated else None)),
    )


def _to_detail(q: models.Question) -> schemas.QuestionDetail:
    return schemas.QuestionDetail(
        id=q.id,
        title=q.title,
        description=q.description,
        category=q.category,
        status=q.status,
        created_at=q.created_at,
        author_username=q.author.username,
        answers=[_to_answer_out(a) for a in q.answers],
    )


@router.get("", response_model=list[schemas.QuestionListItem])
def list_questions(
    category: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(models.Question).options(
        joinedload(models.Question.author), joinedload(models.Question.answers)
    )
    if category:
        query = query.filter(models.Question.category == category)
    if status_filter:
        query = query.filter(models.Question.status == status_filter)
    if search:
        like = f"%{search}%"
        query = query.filter(models.Question.title.ilike(like))
    query = query.order_by(models.Question.created_at.desc()).offset(skip).limit(min(limit, 100))
    return [_to_list_item(q) for q in query.all()]


@router.post("", response_model=schemas.QuestionDetail, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: schemas.QuestionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.category not in schemas.CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of {schemas.CATEGORIES}.")
    question = models.Question(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        user_id=current_user.id,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return _to_detail(question)


@router.get("/{question_id}", response_model=schemas.QuestionDetail)
def get_question(question_id: int, db: Session = Depends(get_db)):
    question = (
        db.query(models.Question)
        .options(
            joinedload(models.Question.author),
            joinedload(models.Question.answers).joinedload(models.Answer.author),
        )
        .filter(models.Question.id == question_id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")
    return _to_detail(question)


@router.post(
    "/{question_id}/answers", response_model=schemas.AnswerOut, status_code=status.HTTP_201_CREATED
)
def post_answer(
    question_id: int,
    payload: schemas.AnswerCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    answer = models.Answer(
        question_id=question.id,
        user_id=current_user.id,
        body=payload.body,
        is_ai_generated=False,
    )
    question.status = "answered"
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return _to_answer_out(answer)


@router.post(
    "/{question_id}/ai-answer", response_model=schemas.AnswerOut, status_code=status.HTTP_201_CREATED
)
def request_ai_answer(
    question_id: int,
    current_user: models.User = Depends(get_current_user),  # must be logged in to avoid abuse
    db: Session = Depends(get_db),
):
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    try:
        answer_text = generate_ai_answer(
            db, title=question.title, description=question.description, category=question.category
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    answer = models.Answer(
        question_id=question.id,
        user_id=None,
        body=answer_text,
        is_ai_generated=True,
    )
    question.status = "answered"
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return _to_answer_out(answer)
