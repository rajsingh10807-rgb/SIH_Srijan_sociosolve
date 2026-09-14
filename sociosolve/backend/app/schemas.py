import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

CATEGORIES = [
    "Water",
    "Health",
    "Agriculture",
    "Energy",
    "Education",
    "Environment",
    "Infrastructure",
    "Other",
]

# ---------- Auth / Users ----------


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_admin: bool
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Answers ----------


class AnswerCreate(BaseModel):
    body: str = Field(min_length=2, max_length=5000)


class AnswerOut(BaseModel):
    id: int
    question_id: int
    body: str
    is_ai_generated: bool
    created_at: datetime.datetime
    author_username: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------- Questions ----------


class QuestionCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    category: str = "Other"


class QuestionListItem(BaseModel):
    id: int
    title: str
    category: str
    status: str
    created_at: datetime.datetime
    author_username: str
    answer_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class QuestionDetail(BaseModel):
    id: int
    title: str
    description: str
    category: str
    status: str
    created_at: datetime.datetime
    author_username: str
    answers: list[AnswerOut] = []

    model_config = ConfigDict(from_attributes=True)


# ---------- Admin: API keys & settings ----------


class ApiKeyCreate(BaseModel):
    key_value: str = Field(min_length=10, max_length=255)
    label: str | None = None
    make_active: bool = True


class ApiKeyOut(BaseModel):
    id: int
    provider: str
    label: str | None
    masked_key: str
    is_active: bool
    added_at: datetime.datetime
    last_used_at: datetime.datetime | None
    last_error: str | None
    last_error_at: datetime.datetime | None

    model_config = ConfigDict(from_attributes=True)


class SettingsOut(BaseModel):
    active_model: str


class SettingsUpdate(BaseModel):
    active_model: str = Field(min_length=2, max_length=100)


class AdminStats(BaseModel):
    total_users: int
    total_questions: int
    total_answers: int
    ai_answers: int
    open_questions: int
    active_key_present: bool
    active_model: str
