from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

# 共享属性
class UltrasoundImageBase(BaseModel):
    image_type: int = Field(..., ge=0, le=6)  # 0=二维，1=M型，2=彩色多普勒，4=组织多普勒，5=脉冲频谱，6=连续频谱
    file_path: str = Field(..., min_length=1, max_length=500)

# 通过API创建时接收的属性
class UltrasoundImageCreate(UltrasoundImageBase):
    case_id: int

# 通过API更新时接收的属性
class UltrasoundImageUpdate(UltrasoundImageBase):
    image_type: Optional[int] = Field(None, ge=0, le=6)
    file_path: Optional[str] = Field(None, min_length=1, max_length=500)

# 存储在数据库中的模型共享的属性
class UltrasoundImageInDBBase(UltrasoundImageBase):
    id: int
    case_id: int
    upload_time: datetime
    
    class Config:
        from_attributes = True  # 原来是 orm_mode = True

# 返回给客户端的属性
class UltrasoundImage(UltrasoundImageInDBBase):
    pass

# 存储在数据库中的属性
class UltrasoundImageInDB(UltrasoundImageInDBBase):
    pass