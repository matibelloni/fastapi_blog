from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .. import models
from ..auth import (
    CurrentUser,
    create_access_token,
    hash_password,
    verify_password,
)
from ..config import settings
from ..database import DbSession
from ..queries import find_user
from ..schemas import (
    RecordResponse,
    Token,
    UserCreate,
    UserPrivate,
    UserPublic,
    UserUpdate,
)

router = APIRouter()


def ensure_self(user_id: int, current_user: models.User, action: str) -> None:
    if user_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail=f"Not authorized to {action} this user"
        )


@router.post("", response_model=UserPrivate, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: DbSession):
    result = await db.scalars(
        select(models.User).where(
            (models.User.username == user.username) | (models.User.email == user.email)
        )
    )
    existing = result.first()
    if existing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Username or email already exists"
        )

    new_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
    result = await db.scalars(
        select(models.User).where(models.User.email == form_data.username.lower())
    )
    user = result.first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserPrivate)
async def get_current_user(current_user: CurrentUser):
    return current_user


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: int, db: DbSession):
    return await find_user(db, user_id)


@router.get("/{user_id}/records", response_model=list[RecordResponse])
async def get_user_records(user_id: int, db: DbSession):
    await find_user(db, user_id)
    result = await db.scalars(
        select(models.ServiceRecord)
        .options(selectinload(models.ServiceRecord.owner))
        .where(models.ServiceRecord.user_id == user_id)
        .order_by(models.ServiceRecord.service_date.desc())
    )
    return result.all()


@router.patch("/{user_id:int}", response_model=UserPrivate)
async def update_user_partial(
    user_id: int, data: UserUpdate, current_user: CurrentUser, db: DbSession
):
    ensure_self(user_id, current_user, "patch")
    user = current_user
    if (
        data.username is not None
        and data.username != user.username
        and (
            await db.scalars(
                select(models.User).where(models.User.username == data.username)
            )
        ).first()
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Username already exists"
        )
    if (
        data.email is not None
        and data.email != user.email
        and (
            await db.scalars(select(models.User).where(models.User.email == data.email))
        ).first()
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Email already exists")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id:int}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, current_user: CurrentUser, db: DbSession):
    ensure_self(user_id, current_user, "delete")
    await db.delete(current_user)
    await db.commit()
