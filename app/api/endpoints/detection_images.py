import os
import shutil
from typing import Any, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.models import Case, DetectionImage, DetectionResult, User
from app.schemas.detection_image import DetectionImage as DetectionImageSchema, DetectionImageCreate

router = APIRouter()

@router.post("/", response_model=DetectionImageSchema, summary="上传检测图像", description="上传检测结果的图像")
async def upload_detection_image(
    *,
    db: Session = Depends(get_db),
    result_id: int,
    image_type: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Upload a new detection image.
    """
    # Check if detection result exists
    detection_result = db.query(DetectionResult).filter(DetectionResult.id == result_id).first()
    if not detection_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection result not found",
        )
    
    # Check if the result belongs to a case owned by the user
    case = db.query(Case).filter(Case.id == detection_result.case_id).first()
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(settings.UPLOAD_DIRECTORY, f"case_{case.id}", f"result_{result_id}")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create detection image record
    detection_image = DetectionImage(
        result_id=result_id,
        image_type=image_type,
        file_path=file_path,
    )
    db.add(detection_image)
    db.commit()
    db.refresh(detection_image)
    
    return detection_image

@router.get("/", response_model=List[DetectionImageSchema], summary="获取检测图像列表", description="获取指定检测结果的图像列表")
def read_detection_images(
    *,
    db: Session = Depends(get_db),
    result_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve detection images for a result.
    """
    # Check if detection result exists
    detection_result = db.query(DetectionResult).filter(DetectionResult.id == result_id).first()
    if not detection_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection result not found",
        )
    
    # Check if the result belongs to a case owned by the user
    case = db.query(Case).filter(Case.id == detection_result.case_id).first()
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    detection_images = db.query(DetectionImage).filter(DetectionImage.result_id == result_id).all()
    return detection_images

@router.get("/{image_id}", response_model=DetectionImageSchema, summary="获取检测图像详情", description="获取指定检测图像的详细信息")
def read_detection_image(
    *,
    db: Session = Depends(get_db),
    image_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get detection image by ID.
    """
    detection_image = db.query(DetectionImage).filter(DetectionImage.id == image_id).first()
    if not detection_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection image not found",
        )
    
    # Check if the image belongs to a result of a case owned by the user
    detection_result = db.query(DetectionResult).filter(DetectionResult.id == detection_image.result_id).first()
    case = db.query(Case).filter(Case.id == detection_result.case_id).first()
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    return detection_image

@router.delete("/{image_id}", response_model=DetectionImageSchema, summary="删除检测图像", description="删除指定检测图像")
def delete_detection_image(
    *,
    db: Session = Depends(get_db),
    image_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete a detection image.
    """
    detection_image = db.query(DetectionImage).filter(DetectionImage.id == image_id).first()
    if not detection_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection image not found",
        )
    
    # Check if the image belongs to a result of a case owned by the user
    detection_result = db.query(DetectionResult).filter(DetectionResult.id == detection_image.result_id).first()
    case = db.query(Case).filter(Case.id == detection_result.case_id).first()
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Delete the file
    if os.path.exists(detection_image.file_path):
        os.remove(detection_image.file_path)
    
    # Delete the record
    db.delete(detection_image)
    db.commit()
    
    return detection_image