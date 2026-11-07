from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import models
from .database import Base, DbSession, engine
from .queries import find_record, find_user
from .routers import records, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(records.router, prefix="/api/records", tags=["records"])


# --- HTML routes ---


@app.get("/", include_in_schema=False)
async def home(request: Request, db: DbSession):
    result = await db.scalars(
        select(models.ServiceRecord)
        .options(selectinload(models.ServiceRecord.owner))
        .order_by(models.ServiceRecord.service_date.desc())
    )
    all_records = result.all()
    return templates.TemplateResponse(
        request, "home.html", {"records": all_records, "title": "Home"}
    )


@app.get("/records/{record_id}", include_in_schema=False)
async def record_page(request: Request, record_id: int, db: DbSession):
    record = await find_record(db, record_id)
    return templates.TemplateResponse(
        request, "record.html", {"record": record, "title": record.title}
    )


@app.get("/users/{user_id}/records", include_in_schema=False, name="user_records")
async def user_records_page(request: Request, user_id: int, db: DbSession):
    user = await find_user(db, user_id)
    result = await db.scalars(
        select(models.ServiceRecord)
        .options(selectinload(models.ServiceRecord.owner))
        .where(models.ServiceRecord.user_id == user_id)
        .order_by(models.ServiceRecord.service_date.desc())
    )
    return templates.TemplateResponse(
        request,
        "user_records.html",
        {"records": result.all(), "user": user, "title": f"{user.username}'s records"},
    )


@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@app.get("/register", include_in_schema=False)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})


@app.get("/account", include_in_schema=False)
async def account_page(request: Request):
    return templates.TemplateResponse(request, "account.html", {"title": "Account"})


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
