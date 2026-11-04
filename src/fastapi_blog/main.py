from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import models
from .database import Base, engine, get_db
from .schemas import (
    RecordCreate,
    RecordResponse,
    RecordUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)

Base.metadata.create_all(bind=engine)

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
DbSession = Annotated[Session, Depends(get_db)]


def find_user(db: Session, user_id: int) -> models.User:
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def find_record(db: Session, record_id: int) -> models.ServiceRecord:
    record = db.get(models.ServiceRecord, record_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Record not found")
    return record


# --- HTML routes ---


@app.get("/", include_in_schema=False)
def home(request: Request, db: DbSession):
    records = db.scalars(select(models.ServiceRecord)).all()
    return templates.TemplateResponse(
        request, "home.html", {"records": records, "title": "Home"}
    )


@app.get("/records/{record_id}", include_in_schema=False)
def record_page(request: Request, record_id: int, db: DbSession):
    record = find_record(db, record_id)
    return templates.TemplateResponse(
        request, "record.html", {"record": record, "title": record.title}
    )


# --- API routes ---


@app.post(
    "/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def create_user(user: UserCreate, db: DbSession):
    existing = db.scalars(
        select(models.User).where(
            (models.User.username == user.username) | (models.User.email == user.email)
        )
    ).first()
    if existing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Username or email already exists"
        )

    new_user = models.User(**user.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: DbSession):
    return find_user(db, user_id)


@app.get("/api/users/{user_id}/records", response_model=list[RecordResponse])
def get_user_records(user_id: int, db: DbSession):
    return find_user(db, user_id).records


@app.patch("/api/users/{user_id:int}", response_model=UserResponse)
def update_user_partial(user_id: int, data: UserUpdate, db: DbSession):
    user = find_user(db, user_id)
    if data.username is not None and data.username != user.username:
        if db.scalars(
            select(models.User).where(models.User.username == data.username)
        ).first():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Username already exists"
            )
    if data.email is not None and data.email != user.email:
        if db.scalars(
            select(models.User).where(models.User.email == data.email)
        ).first():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Email already exists"
            )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@app.delete("/api/users/{user_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: DbSession):
    user = find_user(db, user_id)
    db.delete(user)
    db.commit()


@app.get("/api/records", response_model=list[RecordResponse])
def get_records(db: DbSession):
    return db.scalars(select(models.ServiceRecord)).all()


@app.get("/api/records/{record_id:int}", response_model=RecordResponse)
def get_record(db: DbSession, record_id: int):
    return find_record(db, record_id)


@app.get("/api/records/latest", response_model=RecordResponse)
def get_latest_record(db: DbSession):
    record = db.scalars(
        select(models.ServiceRecord).order_by(models.ServiceRecord.service_date.desc())
    ).first()
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No records yet")
    return record


@app.post(
    "/api/records", response_model=RecordResponse, status_code=status.HTTP_201_CREATED
)
def create_record(record: RecordCreate, db: DbSession):
    find_user(db, record.user_id)
    new_record = models.ServiceRecord(**record.model_dump())
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record


@app.put("/api/records/{record_id:int}", response_model=RecordResponse)
def update_record(record_id: int, data: RecordCreate, db: DbSession):
    record = find_record(db, record_id)
    if data.user_id != record.user_id:
        find_user(db, data.user_id)
    for field, value in data.model_dump().items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@app.patch("/api/records/{record_id:int}", response_model=RecordResponse)
def update_record_partial(record_id: int, data: RecordUpdate, db: DbSession):
    record = find_record(db, record_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@app.delete("/api/records/{record_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(record_id: int, db: DbSession):
    record = find_record(db, record_id)
    db.delete(record)
    db.commit()


# --- Exception handlers ---


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exc)
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exc.status_code,
            "message": exc.detail,
            "title": exc.status_code,
        },
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exc)
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request.",
            "title": "Invalid request",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
