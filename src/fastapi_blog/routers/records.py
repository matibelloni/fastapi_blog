from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .. import models
from ..database import DbSession
from ..queries import find_record, find_user
from ..schemas import RecordCreate, RecordResponse, RecordUpdate

router = APIRouter()


@router.get("", response_model=list[RecordResponse])
async def get_records(db: DbSession):
    result = await db.scalars(
        select(models.ServiceRecord).options(selectinload(models.ServiceRecord.owner))
    )
    return result.all()


@router.get("/{record_id:int}", response_model=RecordResponse)
async def get_record(db: DbSession, record_id: int):
    return await find_record(db, record_id)


@router.get("/latest", response_model=RecordResponse)
async def get_latest_record(db: DbSession):
    result = await db.scalars(
        select(models.ServiceRecord)
        .options(selectinload(models.ServiceRecord.owner))
        .order_by(models.ServiceRecord.service_date.desc())
    )
    record = result.first()
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No records yet")
    return record


@router.post("", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
async def create_record(record: RecordCreate, db: DbSession):
    await find_user(db, record.user_id)
    new_record = models.ServiceRecord(**record.model_dump())
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record, attribute_names=["owner"])
    return new_record


@router.put("/{record_id:int}", response_model=RecordResponse)
async def update_record(record_id: int, data: RecordCreate, db: DbSession):
    record = await find_record(db, record_id)
    if data.user_id != record.user_id:
        await find_user(db, data.user_id)
    for field, value in data.model_dump().items():
        setattr(record, field, value)
    await db.commit()
    await db.refresh(record, attribute_names=["owner"])
    return record


@router.patch("/{record_id:int}", response_model=RecordResponse)
async def update_record_partial(record_id: int, data: RecordUpdate, db: DbSession):
    record = await find_record(db, record_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    await db.commit()
    await db.refresh(record, attribute_names=["owner"])
    return record


@router.delete("/{record_id:int}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_record(record_id: int, db: DbSession):
    record = await find_record(db, record_id)
    await db.delete(record)
    await db.commit()
