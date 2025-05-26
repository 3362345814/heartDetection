# %%
import os
from datetime import datetime
from io import BytesIO

import requests
import torch
import torch.nn as nn
from PIL import Image
from sqlalchemy.orm import Session
from torch.nn import functional as F
from torchvision import models, transforms

from app.models.models import Case, DetectionResult, UltrasoundImage
from app.services.ocr_service import UltrasoundReport
from app.utils.cos import upload_file_to_cos


class ModelService:
    """与心脏疾病检测模型交互的服务类"""

    @classmethod
    async def detect_disease(cls, db: Session, case_id: int) -> DetectionResult:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"病例不存在: ID {case_id}")

        images = db.query(UltrasoundImage).filter(UltrasoundImage.case_id == case_id).all()
        if not images:
            raise ValueError(f"病例 ID {case_id} 没有关联的超声图像")

        # 第一步：获取每张图的推理输出
        prediction_outputs = cls._predict_case(images)

        # 第二步：得出结论和置信度
        conclusion, confidence = cls._finalize_conclusion(prediction_outputs)
        if conclusion == "mild":
            conclusion = "二尖瓣反流（轻度）"
        elif conclusion == "moderate":
            conclusion = "二尖瓣反流（中度）"

        # 第三步：插入或更新检测结果
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

        # 第四步：生成 GradCAM++ 并保存
        for output in prediction_outputs:
            cls.generate_gradcam_and_save(
                model=output["model"],
                input_tensor=output["input_tensor"],
                pred_class=output["pred_class"],
                image=output["image"],
                image_type=output["image_type"] + 4,
                case_id=case_id,
                detection_result_id=detection_result.id,
                db=db
            )

        # 第五步：分割 & 报告文本生成
        cls.segment_and_save_masks(db, case_id, detection_result.id, conclusion)

        image_map = {img.image_type: img.file_path for img in images if img.image_type in [5, 6, 7, 8, 9, 10]}
        if image_map:
            report_map = UltrasoundReport.report(image_map)
            detection_result.description = report_map["description"]
            if report_map["conclusion"] != "":
                detection_result.conclusion = report_map["conclusion"] + "，" + detection_result.conclusion
            db.commit()

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
    def _predict_case(cls, images) -> list[dict]:
        model_files = {
            '2d_apical': 'models/2d_apical.pth',
            '2d_long_axis': 'models/2d_long_axis.pth',
            'doppler_apical': 'models/doppler_apical.pth',
            'doppler_long_axis': 'models/doppler_long_axis.pth'
        }

        results = []

        for image in images:
            image_type_key = cls._map_image_type_to_model_key(image.image_type)
            if image_type_key not in model_files:
                continue

            model_path = model_files[image_type_key]
            if not os.path.exists(model_path):
                continue

            model = models.resnet50(pretrained=False)
            model.fc = nn.Linear(model.fc.in_features, 2)
            model.load_state_dict(torch.load(model_path, map_location=cls.device))
            model = model.to(cls.device)
            model.eval()

            img_response = requests.get(image.file_path)
            img = Image.open(BytesIO(img_response.content)).convert('RGB')
            input_tensor = cls.transform(img).unsqueeze(0).to(cls.device)

            with torch.no_grad():
                output = model(input_tensor)
                probs = F.softmax(output, dim=1)
                prob_values = probs.squeeze().tolist()
                _, pred = torch.max(output, 1)

            results.append({
                "model": model,
                "input_tensor": input_tensor,
                "pred_class": pred.item(),
                "image": img.copy(),
                "image_type": image.image_type,
                "pred_label": cls.class_names[pred.item()],
                "prob": prob_values[pred.item()]
            })

        if not results:
            raise ValueError("没有可用于推理的图像")

        return results

    @classmethod
    def _finalize_conclusion(cls, outputs: list[dict]) -> tuple[str, float]:
        predictions = [o["pred_label"] for o in outputs]
        confidence_scores = [(o["pred_label"], o["prob"]) for o in outputs]

        mild_count = predictions.count('mild')
        final_conclusion = 'mild' if mild_count >= len(predictions) / 2 else 'moderate'

        final_confidences = [score for label, score in confidence_scores if label == final_conclusion]
        avg_confidence = sum(final_confidences) / len(final_confidences) if final_confidences else 0.0

        return final_conclusion, avg_confidence

    @classmethod
    def generate_gradcam_and_save(cls, model, input_tensor, pred_class: int, image: Image.Image,
                                  image_type: int, case_id: int, detection_result_id: int, db: Session):
        from torchcam.methods import GradCAMpp
        import numpy as np

        # 创建 Grad-CAM++ 提取器
        cam_extractor = GradCAMpp(model, target_layer="layer3")
        output = model(input_tensor)  # 得到模型输出 logits
        activation_map = cam_extractor(pred_class, scores=output)[0].cpu().numpy()
        if activation_map.ndim == 3:
            activation_map = activation_map.squeeze(0)
        activation_map = (activation_map - activation_map.min()) / (activation_map.max() - activation_map.min())

        # 着色
        import matplotlib
        colormap = matplotlib.colormaps['jet']
        colored_map = colormap(activation_map)[:, :, :3]
        colored_map = (colored_map * 255).astype(np.uint8)
        colored_map = Image.fromarray(colored_map).resize(image.size)

        # 融合热力图
        heatmap = Image.blend(image, colored_map, alpha=0.5)

        # 保存为 buffer
        buf = BytesIO()
        heatmap.save(buf, format='PNG')
        buf.seek(0)

        # 上传到 COS
        save_path = upload_file_to_cos(buf, f"gradcam_{image_type}.png", content_type="image/png",
                                       path_prefix=f"gradcam/case_{case_id}/result_{detection_result_id}")

        # 保存到数据库
        from app.models.models import DetectionImage
        existing = db.query(DetectionImage).filter_by(result_id=detection_result_id, image_type=image_type).first()
        if existing:
            existing.file_path = save_path
            existing.created_at = datetime.utcnow()
        else:
            db.add(DetectionImage(
                result_id=detection_result_id,
                image_type=image_type,
                file_path=save_path,
                created_at=datetime.utcnow()
            ))
        db.commit()

    @classmethod
    def segment_and_save_masks(cls, db: Session, case_id: int, detection_result_id: int, conclusion: str) -> None:
        from app.models.models import DetectionImage
        from matplotlib import pyplot as plt
        import numpy as np
        import segmentation_models_pytorch as smp
        from torchvision import transforms
        import torch
        from PIL import Image
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
                "class_names": ['LA', 'LV', 'RV', 'AV', 'MV', 'LVOT']
            },
            3: {
                "path": "models/doppler_apical_reflux.pth",
                "class_names": ['MV', 'TV', 'Aorta']
            },
            4: {
                "path": "models/doppler_long_axis_reflux.pth",
                "class_names": ['MV', 'Aorta']
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
            img_response = requests.get(record.file_path)
            image = Image.open(BytesIO(img_response.content)).convert("RGB")
            tensor = transform(image).unsqueeze(0).to(device)
            with torch.no_grad():
                output = model(tensor)[0]
            pred_mask = output.argmax(0).byte().cpu().numpy()
            overlay = overlay_mask(image, pred_mask, class_names)

            plt.figure(figsize=(8, 8))
            plt.imshow(overlay)
            handles = [plt.Rectangle((0, 0), 1, 1, color=np.array(c) / 255) for c in
                       [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]]
            plt.legend(handles, class_names)
            plt.axis("off")
            plt.tight_layout()

            buf = BytesIO()
            plt.savefig(buf, format='png')
            plt.close()
            buf.seek(0)

            save_path = upload_file_to_cos(buf, f"seg_{record.image_type}.png", content_type="image/png",
                                           path_prefix=f"segmentation/case_{case_id}/result_{detection_result_id}")

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

            if record.image_type == 3 or record.image_type == 4:
                threshold = 100

                # Check for TV reflux
                if "TV" in class_names:
                    tv_index = class_names.index("TV") + 1
                    print((pred_mask == tv_index).sum(), threshold)
                    if (pred_mask == tv_index).sum() > threshold and "三尖瓣反流" not in conclusion:
                        conclusion += "，三尖瓣反流"

                # Check for Aorta reflux
                if "Aorta" in class_names:
                    ao_index = class_names.index("Aorta") + 1
                    if (pred_mask == ao_index).sum() > threshold and "主动脉瓣反流" not in conclusion:
                        conclusion += "，主动脉瓣反流"
        db.commit()

        detection_result = db.query(DetectionResult).filter_by(id=detection_result_id).first()
        if detection_result:
            detection_result.conclusion = conclusion
            db.commit()
