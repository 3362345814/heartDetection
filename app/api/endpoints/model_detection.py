# app/api/endpoints/model_detection.py
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.endpoints.detection_results import read_detection_results_with_image
from app.models.models import Case, User
from app.services.model_service import ModelService
from app.utils.pdf_generator import generate_pdf_report  # 确保你有这个模块

router = APIRouter()


@router.post("/{case_id}/detect", summary="执行疾病检测",
             description="对指定病例调用AI模型进行疾病检测并生成结果")
async def detect_disease(
        *,
        db: Session = Depends(get_db),
        case_id: int,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    对指定病例调用AI模型进行疾病检测
    """
    # 检查病例是否存在并且属于当前用户
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="病例不存在",
        )
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有足够的权限",
        )

    try:
        # 调用模型服务进行疾病检测
        await ModelService.detect_disease(db, case_id)
        result = read_detection_results_with_image(case_id=case_id, db=db, current_user=current_user)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检测过程中发生错误: {str(e)}",
        )


@router.get("/{case_id}/report", summary="生成诊断报告 PDF",
            description="根据病例ID生成诊断报告PDF文件，并返回文件")
def generate_report_pdf(
        *,
        db: Session = Depends(get_db),
        case_id: int,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    根据病例ID生成诊断报告PDF并返回
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="病例不存在",
        )
    if case.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有足够的权限",
        )

    try:
        cos_url = generate_pdf_report(case)
        return {"report_url": cos_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成报告过程中发生错误: {str(e)}",
        )
