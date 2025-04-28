from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, get_db
from app.models.models import Case, DetectionResult, User
from app.schemas.detection_result import DetectionResult as DetectionResultSchema, DetectionResultCreate, \
    DetectionResultUpdate

router = APIRouter()


@router.post("/", response_model=DetectionResultSchema, summary="创建检测结果", description="创建一个新的检测结果")
def create_detection_result(
        *,
        db: Session = Depends(get_db),
        result_in: DetectionResultCreate,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create a new detection result.
    """
    # Check if case exists and belongs to the user
    case = db.query(Case).filter(Case.id == result_in.case_id).first()
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

    # Create detection result
    detection_result = DetectionResult(
        case_id=result_in.case_id,
        conclusion=result_in.conclusion,
        description=result_in.description,
        confidence=result_in.confidence,
    )
    db.add(detection_result)
    db.commit()
    db.refresh(detection_result)

    return detection_result


@router.get("/", response_model=List[DetectionResultSchema], summary="获取检测结果列表",
            description="获取指定病例的检测结果列表")
def read_detection_results(
        *,
        db: Session = Depends(get_db),
        case_id: int,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve detection results for a case.
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

    detection_results = db.query(DetectionResult).filter(DetectionResult.case_id == case_id).all()
    return detection_results


@router.get("/{result_id}", response_model=DetectionResultSchema, summary="获取检测结果详情",
            description="获取指定检测结果的详细信息")
def read_detection_result(
        *,
        db: Session = Depends(get_db),
        result_id: int,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get detection result by ID.
    """
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

    return detection_result


@router.put("/{result_id}", response_model=DetectionResultSchema, summary="更新检测结果",
            description="更新指定检测结果的信息")
def update_detection_result(
        *,
        db: Session = Depends(get_db),
        result_id: int,
        result_in: DetectionResultUpdate,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update a detection result.
    """
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

    update_data = result_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(detection_result, field, value)

    db.add(detection_result)
    db.commit()
    db.refresh(detection_result)

    return detection_result


@router.delete("/{result_id}", response_model=DetectionResultSchema, summary="删除检测结果",
               description="删除指定检测结果")
def delete_detection_result(
        *,
        db: Session = Depends(get_db),
        result_id: int,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete a detection result.
    """
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

    db.delete(detection_result)
    db.commit()

    return detection_result


# 新增接口：获取检测结果及图像信息
@router.get("/case/{case_id}", summary="获取检测结果及图像", description="通过case_id获取检测结果，并拼接检测图像信息")
def read_detection_results_with_image(
        *,
        db: Session = Depends(get_db),
        case_id: int,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve detection results and associated images for a case.
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

    detection_results = (
        db.query(DetectionResult)
        .options(joinedload(DetectionResult.detection_images))
        .filter(DetectionResult.case_id == case_id)
        .all()
    )

    # 格式化返回，包含detection_result和detection_image内容
    results_with_images = []
    for result in detection_results:
        result_data = {
            "id": result.id,
            "case_id": result.case_id,
            "conclusion": result.conclusion,
            "description": result.description,
            "confidence": result.confidence,
            "images": [
                {
                    "id": img.id,
                    "result_id": img.result_id,
                    "image_type": img.image_type,
                    "file_path": img.file_path,
                } for img in result.detection_images
            ] if result.detection_images else [],
        }
        results_with_images.append(result_data)

    return results_with_images
