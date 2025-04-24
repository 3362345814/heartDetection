import os
import shutil
from typing import Any, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.models import Case, UltrasoundImage, User
from app.schemas.ultrasound_image import UltrasoundImage as UltrasoundImageSchema, UltrasoundImageCreate

router = APIRouter()

@router.post("/", response_model=UltrasoundImageSchema, summary="上传超声图像", description="上传超声图像")
async def upload_ultrasound_image(
    *,
    db: Session = Depends(get_db),
    case_id: int,
    image_type: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Upload a new ultrasound image.
    """
    # Check if case exists and belongs to the user
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(settings.UPLOAD_DIRECTORY, f"case_{case_id}")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create ultrasound image record
    ultrasound_image = UltrasoundImage(
        case_id=case_id,
        image_type=image_type,
        file_path=file_path,
    )
    db.add(ultrasound_image)
    db.commit()
    db.refresh(ultrasound_image)
    
    return ultrasound_image

@router.get("/", response_model=List[UltrasoundImageSchema], summary="获取超声图像列表", description="获取指定病例的超声图像列表")
def read_ultrasound_images(
    *,
    db: Session = Depends(get_db),
    case_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve ultrasound images for a case.
    """
    # Check if case exists and belongs to the user
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    ultrasound_images = db.query(UltrasoundImage).filter(UltrasoundImage.case_id == case_id).all()
    return ultrasound_images

@router.get("/{image_id}", response_model=UltrasoundImageSchema, summary="获取超声图像详情", description="获取指定超声图像的详细信息")
def read_ultrasound_image(
    *,
    db: Session = Depends(get_db),
    image_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get ultrasound image by ID.
    """
    ultrasound_image = db.query(UltrasoundImage).filter(UltrasoundImage.id == image_id).first()
    if not ultrasound_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ultrasound image not found",
        )
    
    # Check if the image belongs to a case owned by the user
    case = db.query(Case).filter(Case.id == ultrasound_image.case_id).first()
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    return ultrasound_image

@router.delete("/{image_id}", response_model=UltrasoundImageSchema, summary="删除超声图像", description="删除指定超声图像")
def delete_ultrasound_image(
    *,
    db: Session = Depends(get_db),
    image_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete an ultrasound image.
    """
    ultrasound_image = db.query(UltrasoundImage).filter(UltrasoundImage.id == image_id).first()
    if not ultrasound_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ultrasound image not found",
        )
    
    # Check if the image belongs to a case owned by the user
    case = db.query(Case).filter(Case.id == ultrasound_image.case_id).first()
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Delete the file
    if os.path.exists(ultrasound_image.file_path):
        os.remove(ultrasound_image.file_path)
    
    # Delete the record
    db.delete(ultrasound_image)
    db.commit()
    
    return ultrasound_image