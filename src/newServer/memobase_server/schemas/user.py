from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr
 
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
 
class UserCreate(UserBase):
    password: str
 
class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
 
    class Config:
        from_attributes = True