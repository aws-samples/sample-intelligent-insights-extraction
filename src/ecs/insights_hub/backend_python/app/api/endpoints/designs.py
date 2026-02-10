from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.services.opensearch_service import OpenSearchService
from app.models.design import Design, DesignDetail, DesignSearchParams
from app.utils.logger import logger

router = APIRouter()

aos_service = OpenSearchService()

# 收藏请求的数据模型
class FavoriteRequest(BaseModel):
    design_id: str
    favoriteUser: str

# 收藏响应的数据模型
class FavoriteResponse(BaseModel):
    success: bool
    message: str

@router.post("/designs/favorite", response_model=FavoriteResponse)
async def favorite_design(request: FavoriteRequest):
    """
    收藏设计
    """
    try:
        result = aos_service.favorite_designs(request.design_id, request.favoriteUser)
        return FavoriteResponse(
            success=True,
            message=result
        )
    except Exception as e:
        logger.error(f"Error in favorite endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/designs/searchFavorite", response_model=List[Design])
async def search_favorite_designs(user_name: str = Query(..., description="user name")):
    """
    通过用户名搜索收藏的设计
    """
    try:
        designs = aos_service.search_favorite_designs(user_name)
        return designs
    except Exception as e:
        logger.error(f"Error in search_favorite_designs endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/designs/search", response_model=List[Design])
async def search_designs(q: str = Query(..., description="搜索查询")):
    """
    通过查询字符串搜索设计
    """
    try:
        designs = aos_service.search_designs(q)
        return designs
    except Exception as e:
        logger.error(f"Error in search_designs endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/designs", response_model=List[Design])
async def get_all_designs(
    tag: Optional[str] = Query(None, description="按标签过滤设计"),
    limit: int = Query(20, description="返回设计的数量"),
    page: int = Query(1, description="页码")
):
    """
    获取所有设计，可选择按标签过滤
    """
    try:
        designs = aos_service.get_all_designs(tag=tag, limit=limit, page=page)
        return designs
    except Exception as e:
        logger.error(f"Error in get_all_designs endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/designs/{design_id}", response_model=DesignDetail)
async def get_design_by_id(design_id: str):
    """
    通过ID获取设计
    """
    try:
        design = aos_service.get_design_by_id(design_id)
        if not design:
            raise HTTPException(status_code=404, detail=f"Design with ID {design_id} not found")
        return design
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_design_by_id endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
