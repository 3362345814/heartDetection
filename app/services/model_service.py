# %%
import os
from datetime import datetime

import torch
import torch.nn as nn
from PIL import Image
from sqlalchemy.orm import Session
from torch.nn import functional as F
from torchvision import models, transforms

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

        conclusion, confidence = cls._predict_case(images)

        detection_result = DetectionResult(
            case_id=case_id,
            conclusion=conclusion,
            description="",
            confidence=confidence,
            result_time=datetime.utcnow()
        )

        db.add(detection_result)
        db.commit()
        db.refresh(detection_result)

        return detection_result

    class_names = ['mild', 'moderate']
    device = torch.device('mps') if torch.backends.mps.is_available() else torch.device('cpu')
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406],
                             [0.229, 0.224, 0.225])
    ])

    @staticmethod
    def _map_image_type_to_model_key(image_type: int) -> str:
        type_map = {
            0: '2d_apical',
            1: '2d_long_axis',
            2: 'doppler_apical',
            3: 'doppler_long_axis',
        }
        return type_map.get(image_type, None)

    @classmethod
    def _predict_case(cls, images) -> tuple[str, float]:
        model_files = {
            '2d_apical': 'models/2d_apical.pth',
            '2d_long_axis': 'models/2d_long_axis.pth',
            'doppler_apical': 'models/doppler_apical.pth',
            'doppler_long_axis': 'models/doppler_long_axis.pth'
        }

        predictions = []
        confidence_scores = []

        for image in images:
            image_type = cls._map_image_type_to_model_key(image.image_type)
            if image_type not in model_files:
                print(f"警告：未找到与图像类型 {image.image_type} 对应的模型文件")
                continue

            model_path = model_files[image_type]
            if not os.path.exists(image.file_path) or not os.path.exists(model_path):
                print(f"警告：图像文件或模型文件不存在: {image.file_path}, {model_path}")
                continue

            model = models.resnet50(pretrained=False)
            model.fc = nn.Linear(model.fc.in_features, 2)
            model.load_state_dict(torch.load(model_path, map_location=cls.device))
            model = model.to(cls.device)
            model.eval()

            img = Image.open(image.file_path).convert('RGB')
            input_tensor = cls.transform(img).unsqueeze(0).to(cls.device)
            with torch.no_grad():
                output = model(input_tensor)
                probs = F.softmax(output, dim=1)
                prob_values = probs.squeeze().tolist()
                _, pred = torch.max(output, 1)
                pred_label = cls.class_names[pred.item()]
                predictions.append(pred_label)
                confidence_scores.append((pred_label, prob_values[pred.item()]))

        if not predictions:
            raise ValueError("没有可用于推理的图像")

        mild_count = predictions.count('mild')
        final_conclusion = 'mild' if mild_count > len(predictions) / 2 else 'moderate'

        # 计算平均置信度
        final_confidences = [score for label, score in confidence_scores if label == final_conclusion]
        avg_confidence = sum(final_confidences) / len(final_confidences) if final_confidences else 0.0

        return final_conclusion, avg_confidence
