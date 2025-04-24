from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

# 共享属性
class UserBase(BaseModel):
    """用户基础数据模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名，长度3-50字符")

# 通过API创建时接收的属性
class UserCreate(UserBase):
    """创建用户时的数据模型"""
    password: str = Field(..., min_length=8, description="用户密码，最少8个字符")

# 通过API更新时接收的属性
class UserUpdate(UserBase):
    """更新用户信息时的数据模型"""
    password: Optional[str] = Field(None, min_length=8, description="用户密码，最少8个字符，不传则不修改")

# 存储在数据库中的模型共享的属性
class UserInDBBase(UserBase):
    """用户数据库基础模型"""
    id: int = Field(..., description="用户唯一ID")
    created_at: datetime = Field(..., description="用户创建时间")

    class Config:
        from_attributes = True

# 返回给客户端的属性
class User(UserInDBBase):
    """返回给客户端的用户模型"""
    pass

# 存储在数据库中的属性
class UserInDB(UserInDBBase):
    """存储在数据库中的用户完整模型"""
    password: str = Field(..., description="用户密码（哈希存储）")
