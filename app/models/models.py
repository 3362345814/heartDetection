from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base


# 用户模型
class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="用户ID")
    username = Column(String(50), unique=True, nullable=False, comment="用户名，唯一")
    password = Column(String(128), nullable=False, comment="密码（哈希存储）")
    created_at = Column(DateTime, default=datetime.utcnow, comment="注册时间，自动填写")

    cases = relationship("Case", back_populates="user", cascade="all, delete-orphan")


class Case(Base):
    __tablename__ = "case"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="检查案例ID")
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False,
                     comment="外键，上传用户ID，关联 user.id")
    name = Column(String(50), nullable=False, comment="患者姓名")
    gender = Column(Integer, nullable=False, comment="患者性别：0=女，1=男")
    age = Column(Integer, nullable=False, comment="患者年龄")
    notes = Column(Text, nullable=True, comment="病例备注，可空")
    created_at = Column(DateTime, default=datetime.utcnow, comment="上传时间，自动填写")

    # Relationships
    user = relationship("User", back_populates="cases")
    ultrasound_images = relationship("UltrasoundImage", back_populates="case", cascade="all, delete-orphan")
    detection_results = relationship("DetectionResult", back_populates="case", cascade="all, delete-orphan")


class UltrasoundImage(Base):
    __tablename__ = "ultrasound_image"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="图片ID")
    case_id = Column(Integer, ForeignKey("case.id", ondelete="CASCADE"), nullable=False, comment="外键，关联 case.id")
    image_type = Column(Integer, nullable=False,
                        comment="图片类型：0=二维-心尖，1=二维-长轴，2=多普勒-心尖，3=多普勒-长轴，4=二维心房尺寸图，"
                                "5=左心室M型超声图，6=右心室M型超声图，7=左心室组织多普勒图，8=右心室组织多普勒图，7=频谱图")
    file_path = Column(String(500), nullable=False, comment="存储路径（本地或云地址）")
    upload_time = Column(DateTime, default=datetime.utcnow, comment="上传时间，自动填写")

    case = relationship("Case", back_populates="ultrasound_images")


class DetectionResult(Base):
    __tablename__ = "detection_result"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="诊断结果ID")
    case_id = Column(Integer, ForeignKey("case.id", ondelete="CASCADE"), nullable=False, comment="外键，关联 case.id")
    conclusion = Column(Text, nullable=False, comment="诊断结论")
    description = Column(Text, nullable=False, comment="诊断描述，AI生成完整文字解释")
    confidence = Column(Float, nullable=False, comment="置信度，预测概率（0 ~ 1）")
    result_time = Column(DateTime, default=datetime.utcnow, comment="诊断完成时间")

    case = relationship("Case", back_populates="detection_results")
    detection_images = relationship("DetectionImage", back_populates="detection_result", cascade="all, delete-orphan")


class DetectionImage(Base):
    __tablename__ = "detection_image"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="附属图片ID")
    result_id = Column(Integer, ForeignKey("detection_result.id", ondelete="CASCADE"), nullable=False,
                       comment="外键，关联 detection_result.id")
    image_type = Column(Integer, nullable=False, comment="图片类型：0=长轴分割图，1=心尖四腔心分割图，3=反流检测图")
    file_path = Column(String(500), nullable=False, comment="图片路径（本地地址）")
    created_at = Column(DateTime, default=datetime.utcnow, comment="图片生成时间，自动填写")

    detection_result = relationship("DetectionResult", back_populates="detection_images")
