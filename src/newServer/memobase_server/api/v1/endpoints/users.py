from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ....database import get_db
from ....schemas.user import UserCreate, UserResponse
from ....models.user import User
 
router = APIRouter()
 
@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = User(
        email=user.email,
        full_name=user.full_name,
        hashed_password=user.password  # 注意：实际应用中需要加密
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
 
@router.get("/{user_id}", response_model=UserResponse)
async def read_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
 
@router.get("/", response_model=List[UserResponse])
async def read_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    users = await db.execute(select(User).offset(skip).limit(limit))
    return users.scalars().all()