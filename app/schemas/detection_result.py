from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

# 共享属性
class DetectionResultBase(BaseModel):
    conclusion: str
    description: str
    confidence: float = Field(..., ge=0.0, le=1.0)

# 通过API创建时接收的属性
class DetectionResultCreate(DetectionResultBase):
    case_id: int

# 通过API更新时接收的属性
class DetectionResultUpdate(DetectionResultBase):
    conclusion: Optional[str] = None
    description: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

# 存储在数据库中的模型共享的属性
class DetectionResultInDBBase(DetectionResultBase):
    id: int
    case_id: int
    result_time: datetime
    
    class Config:
        from_attributes = True  # 原来是 orm_mode = True

# 返回给客户端的属性
class DetectionResult(DetectionResultInDBBase):
    pass

# 存储在数据库中的属性
class DetectionResultInDB(DetectionResultInDBBase):
    pass