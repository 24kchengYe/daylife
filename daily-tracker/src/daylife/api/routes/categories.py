"""分类路由 - CRUD"""

from fastapi import APIRouter

from daylife.core import crud
from daylife.core.database import get_session
from daylife.core.schemas import (
    ApiResponse,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
)

router = APIRouter()


@router.get("", response_model=ApiResponse[list[CategoryOut]])
def list_categories():
    session = get_session()
    try:
        categories = crud.list_categories(session)
        items = [CategoryOut.model_validate(c) for c in categories]
        return ApiResponse(data=items)
    finally:
        session.close()


@router.post("", response_model=ApiResponse[CategoryOut])
def create_category(data: CategoryCreate):
    session = get_session()
    try:
        existing = crud.get_category_by_name(session, data.name)
        if existing:
            return ApiResponse(code=409, message=f"Category '{data.name}' already exists")
        cat = crud.create_category(
            session, name=data.name, icon=data.icon,
            color=data.color, sort_order=data.sort_order,
        )
        session.commit()
        return ApiResponse(data=CategoryOut.model_validate(cat))
    finally:
        session.close()


@router.put("/{category_id}", response_model=ApiResponse[CategoryOut])
def update_category(category_id: int, data: CategoryUpdate):
    session = get_session()
    try:
        update_fields = data.model_dump(exclude_unset=True)
        if not update_fields:
            return ApiResponse(code=400, message="No fields to update")
        cat = crud.update_category(session, category_id, **update_fields)
        if not cat:
            return ApiResponse(code=404, message="Category not found")
        session.commit()
        return ApiResponse(data=CategoryOut.model_validate(cat))
    finally:
        session.close()


@router.delete("/{category_id}", response_model=ApiResponse)
def delete_category(category_id: int):
    session = get_session()
    try:
        cat = crud.get_category_by_id(session, category_id)
        if not cat:
            return ApiResponse(code=404, message="Category not found")
        session.delete(cat)
        session.commit()
        return ApiResponse(message="Deleted")
    finally:
        session.close()
