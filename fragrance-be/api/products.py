import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from starlette import status

import services.curated_product_service as curated_product_service
from models.product_schema import PaginatedProductResponse

# 네이버 쇼핑 검색 API 종료로 실시간 검색 기반 product_service는 사용 중단.
# 참고/재사용 가능성을 위해 services/product_service.py 파일 자체는 남겨둠 (라우터에서 미사용).

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/fragrances/{product}/products",
    response_model=PaginatedProductResponse,
    summary="제품 전체 향 상품 목록 (페이지네이션)",
    status_code=status.HTTP_200_OK,
)
def get_product_items(
    product: str,
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(20, ge=1, le=100, description="페이지당 결과 수"),
):
    try:
        return curated_product_service.get_product_products_paginated(product, page, per_page)
    except (PyMongoError, ServerSelectionTimeoutError) as exc:
        logger.exception("MongoDB 오류")
        raise HTTPException(status_code=503, detail="MongoDB connection failed.") from exc


@router.get(
    "/fragrances/{product}/{scent_slug}/products",
    response_model=PaginatedProductResponse,
    summary="향 계열별 상품 목록 (페이지네이션)",
    status_code=status.HTTP_200_OK,
)
def get_scent_products(
    product: str,
    scent_slug: str,
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(20, ge=1, le=100, description="페이지당 결과 수"),
    fragrance: Optional[str] = Query(None, description="세부 향 슬러그 (fragrance.html 전용)"),
):
    try:
        return curated_product_service.get_products_paginated(product, scent_slug, fragrance, page, per_page)
    except (PyMongoError, ServerSelectionTimeoutError) as exc:
        logger.exception("MongoDB 오류")
        raise HTTPException(status_code=503, detail="MongoDB connection failed.") from exc
