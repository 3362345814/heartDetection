from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.models import Case, User
from app.schemas.case import Case as CaseSchema, CaseCreate, CaseUpdate

router = APIRouter()


@router.post("/", response_model=CaseSchema, summary="创建病例", description="创建一个新的病例记录")
def create_case(
        *,
        db: Session = Depends(get_db),
        case_in: CaseCreate,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create a new case.
    """
    case = Case(
        user_id=current_user.id,
        name=case_in.name,
        gender=case_in.gender,
        age=case_in.age,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.get("/", response_model=List[CaseSchema], summary="获取病例列表", description="获取当前用户的病例列表")
def read_cases(
        db: Session = Depends(get_db),
        skip: int = 0,
        limit: int = 100,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve cases.
    """
    cases = db.query(Case).filter(Case.user_id == current_user.id).offset(skip).limit(limit).all()
    return cases


@router.get("/{case_id}", response_model=CaseSchema, summary="获取病例详情", description="获取指定病例的详细信息")
def read_case(
        *,
        db: Session = Depends(get_db),
        case_id: int,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get case by ID.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    return case


@router.put("/{case_id}", response_model=CaseSchema, summary="更新病例信息", description="更新指定病例的信息")
def update_case(
        *,
        db: Session = Depends(get_db),
        case_id: int,
        case_in: CaseUpdate,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update a case.
    """
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

    update_data = case_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)

    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.delete("/{case_id}", response_model=CaseSchema, summary="删除病例", description="删除指定病例")
def delete_case(
        *,
        db: Session = Depends(get_db),
        case_id: int,
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete a case.
    """
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

    db.delete(case)
    db.commit()
    return case
