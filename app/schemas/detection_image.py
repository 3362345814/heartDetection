from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# 共享属性
class DetectionImageBase(BaseModel):
    """检测图像基础数据模型"""
    image_type: int = Field(..., description="图像类型：0=分割图，1=热力图，2=血流图，3=其他")
    file_path: str = Field(..., min_length=1, max_length=500, description="图像文件路径")


# 通过API创建时接收的属性
class DetectionImageCreate(DetectionImageBase):
    """创建检测图像时的数据模型"""
    result_id: int = Field(..., description="关联的检测结果ID")


# 通过API更新时接收的属性
class DetectionImageUpdate(DetectionImageBase):
    """更新检测图像时的数据模型"""
    image_type: Optional[int] = Field(None, description="图像类型：0=分割图，1=热力图，2=血流图，3=其他")
    file_path: Optional[str] = Field(None, min_length=1, max_length=500, description="图像文件路径")


# 存储在数据库中的模型共享的属性
class DetectionImageInDBBase(DetectionImageBase):
    """检测图像数据库基础模型"""
    id: int = Field(..., description="检测图像唯一ID")
    result_id: int = Field(..., description="关联的检测结果ID")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


# 返回给客户端的属性
class DetectionImage(DetectionImageInDBBase):
    pass


# 存储在数据库中的属性
class DetectionImageInDB(DetectionImageInDBBase):
    """存储在数据库中的检测图像完整模型"""
    pass
