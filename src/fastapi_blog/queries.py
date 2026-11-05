from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import models


async def find_user(db: AsyncSession, user_id: int) -> models.User:
    user = await db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def find_record(db: AsyncSession, record_id: int) -> models.ServiceRecord:
    record = await db.get(
        models.ServiceRecord,
        record_id,
        options=[selectinload(models.ServiceRecord.owner)],
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Record not found")
    return record
