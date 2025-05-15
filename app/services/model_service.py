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

        description = ""
        if conclusion == "mild":
            description += "二尖瓣反流（轻度）"
        elif conclusion == "moderate":
            description += "二尖瓣反流（中度）"

        detection_result = db.query(DetectionResult).filter_by(case_id=case_id).first()
        if detection_result:
            detection_result.conclusion = conclusion
            detection_result.description = ""
            detection_result.confidence = confidence
            detection_result.result_time = datetime.utcnow()
        else:
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

        cls.segment_and_save_masks(db, case_id, detection_result.id, description)

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
            1: '2d_apical',
            2: '2d_long_axis',
            3: 'doppler_apical',
            4: 'doppler_long_axis'
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

    @classmethod
    def segment_and_save_masks(cls, db: Session, case_id: int, detection_result_id: int, description: str) -> None:
        from app.models.models import DetectionImage
        from matplotlib import pyplot as plt
        import numpy as np
        import segmentation_models_pytorch as smp
        from torchvision import transforms
        import torch
        from PIL import Image
        import os
        from datetime import datetime

        def overlay_mask(image: Image.Image, mask: np.ndarray, class_names: list[str]) -> np.ndarray:
            image = image.resize((512, 512))
            base = np.array(image).copy()
            color_map = [
                (0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255),
                (255, 255, 0), (255, 0, 255), (0, 255, 255),
            ]
            overlay = np.zeros_like(base)
            for idx in range(1, len(class_names) + 1):
                overlay[mask == idx] = color_map[idx % len(color_map)]
            blended = (0.6 * base + 0.4 * overlay).astype(np.uint8)
            return blended

        image_records = db.query(UltrasoundImage).filter(UltrasoundImage.case_id == case_id).all()
        model_configs = {
            1: {
                "path": "models/2d_apical_unetpp.pth",
                "class_names": ['LA', 'LV', 'RA', 'RV', 'MV', 'TV']
            },
            2: {
                "path": "models/2d_long_axis_unetpp.pth",
                "class_names": ['AV', 'LA', 'LV', 'LVOT', 'MV', 'RV']
            },
            3: {
                "path": "models/doppler_apical_reflux.pth",
                "class_names": ['MV', 'TV', 'Aorta']
            }
        }

        for record in image_records:
            config = model_configs.get(record.image_type)
            if not config:
                continue

            class_names = config["class_names"]
            class_count = len(class_names) + 1
            model = smp.UnetPlusPlus(encoder_name="resnet34", encoder_weights=None, in_channels=3, classes=class_count)
            device = cls.device
            model.load_state_dict(torch.load(config["path"], map_location=device))
            model = model.to(device).eval()

            transform = transforms.Compose([
                transforms.Resize((512, 512)),
                transforms.ToTensor()
            ])
            image = Image.open(record.file_path).convert("RGB")
            tensor = transform(image).unsqueeze(0).to(device)
            with torch.no_grad():
                output = model(tensor)[0]
            pred_mask = output.argmax(0).byte().cpu().numpy()
            overlay = overlay_mask(image, pred_mask, class_names)

            # save path
            base_dir = f"uploads/case_{case_id}/result_{detection_result_id}"
            os.makedirs(base_dir, exist_ok=True)
            save_path = os.path.join(base_dir, f"seg_{record.image_type}.png")

            plt.figure(figsize=(8, 8))
            plt.imshow(overlay)
            handles = [plt.Rectangle((0, 0), 1, 1, color=np.array(c) / 255) for c in
                       [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]]
            plt.legend(handles, class_names)
            plt.axis("off")
            plt.tight_layout()
            plt.savefig(save_path)
            plt.close()

            existing = db.query(DetectionImage).filter_by(result_id=detection_result_id,
                                                          image_type=record.image_type).first()
            if existing:
                existing.file_path = save_path
                existing.created_at = datetime.utcnow()
            else:
                db.add(DetectionImage(
                    result_id=detection_result_id,
                    image_type=record.image_type,
                    file_path=save_path,
                    created_at=datetime.utcnow()
                ))

            if record.image_type == 3:
                threshold = 100

                # Check for TV reflux
                if "TV" in class_names:
                    tv_index = class_names.index("TV") + 1
                    print((pred_mask == tv_index).sum(), threshold)
                    if (pred_mask == tv_index).sum() > threshold:
                        description += "，三尖瓣反流"

                # Check for Aorta reflux
                if "Aorta" in class_names:
                    ao_index = class_names.index("Aorta") + 1
                    if (pred_mask == ao_index).sum() > threshold:
                        description += "，主动脉瓣反流"
        db.commit()

        detection_result = db.query(DetectionResult).filter_by(id=detection_result_id).first()
        if detection_result:
            detection_result.description = description
            db.commit()
