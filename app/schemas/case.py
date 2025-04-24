from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

# 共享属性
class CaseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    gender: int = Field(..., ge=0, le=1)  # 0=女性, 1=男性
    age: int = Field(..., ge=0, le=150)

# 通过API创建时接收的属性
class CaseCreate(CaseBase):
    pass

# 通过API更新时接收的属性
class CaseUpdate(CaseBase):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    gender: Optional[int] = Field(None, ge=0, le=1)
    age: Optional[int] = Field(None, ge=0, le=150)

# 存储在数据库中的模型共享的属性
class CaseInDBBase(CaseBase):
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# 返回给客户端的属性
class Case(CaseInDBBase):
    pass

# 存储在数据库中的属性
class CaseInDB(CaseInDBBase):
    pass