# %%
from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session

from app.models.models import Case, DetectionResult, UltrasoundImage


class ModelService:
    """与心脏疾病检测模型交互的服务类"""

    @classmethod
    async def detect_disease(cls, db: Session, case_id: int) -> DetectionResult:
        """
        为指定病例调用疾病检测模型，生成检测结果

        Args:
            db: 数据库会话
            case_id: 病例ID

        Returns:
            DetectionResult: 创建的检测结果对象

        Raises:
            ValueError: 如果病例不存在或病例没有关联的超声图像
        """
        # 获取病例信息
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"病例不存在: ID {case_id}")

        # 获取病例关联的超声图像
        images = db.query(UltrasoundImage).filter(UltrasoundImage.case_id == case_id).all()
        if not images:
            raise ValueError(f"病例 ID {case_id} 没有关联的超声图像")

        # TODO: 实际中这里应该调用模型API或本地模型进行预测
        # 这里仅作示例，返回模拟结果
        prediction = cls._mock_model_prediction(case, images)

        # 创建检测结果
        detection_result = DetectionResult(
            case_id=case_id,
            conclusion=prediction["conclusion"],
            description=prediction["description"],
            confidence=prediction["confidence"],
            result_time=datetime.utcnow()
        )

        db.add(detection_result)
        db.commit()
        db.refresh(detection_result)

        return detection_result

    @staticmethod
    def _mock_model_prediction(case: Case, images: list[UltrasoundImage]) -> Dict[str, Any]:
        """
        模拟模型预测结果（在实际应用中，这里会调用真实的模型）

        Args:
            case: 病例对象
            images: 超声图像列表

        Returns:
            Dict: 包含结论、描述和置信度的字典
        """
        # 这里仅为示例，实际应用中应替换为真实模型调用
        return {
            "conclusion": "心脏舒张功能减低",
            "description": "患者超声图像显示左心室壁运动异常，舒张功能减低。建议进一步检查确认。",
            "confidence": 0.85
        }
