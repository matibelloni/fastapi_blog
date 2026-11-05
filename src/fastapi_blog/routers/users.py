from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .. import models
from ..database import DbSession
from ..queries import find_user
from ..schemas import RecordResponse, UserCreate, UserResponse, UserUpdate

router = APIRouter()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
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

    new_user = models.User(**user.model_dump())
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.get("/{user_id}", response_model=UserResponse)
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


@router.patch("/{user_id:int}", response_model=UserResponse)
async def update_user_partial(user_id: int, data: UserUpdate, db: DbSession):
    user = await find_user(db, user_id)
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
async def delete_user(user_id: int, db: DbSession):
    user = await find_user(db, user_id)
    await db.delete(user)
    await db.commit()
