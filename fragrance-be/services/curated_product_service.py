"""
수동으로 큐레이션한 상품 데이터를 MongoDB `curated_products` 컬렉션에서 읽어 반환한다.

네이버 쇼핑 검색 API가 2026-07-31 종료되고, 대체 API(쿠팡파트너스 등)도
실시간 검색 용도로는 맞지 않아(호출 제한, 이용약관상 목적 불일치) 도입한 방식이다.
데이터는 scripts/import_curated_products.py로 CSV에서 적재한다.
"""

import math
from typing import List, Optional

from database.mongodb import get_curated_products_collection
from models.product_schema import NaverProductItem, PaginatedProductResponse


def _normalize_item(doc: dict) -> dict:
    return {
        "productId": str(doc.get("productId", "")),
        "title": doc.get("title", ""),
        "link": doc.get("link", ""),
        "image": doc.get("image", ""),
        "lprice": str(doc.get("lprice", "")),
        "mallName": doc.get("mallName", ""),
    }


def _dedup_by_product_id(docs: List[dict]) -> List[dict]:
    seen: dict = {}
    for doc in docs:
        pid = doc.get("productId", "")
        if pid and pid not in seen:
            seen[pid] = doc
    return list(seen.values())


def _paginate(items: List[dict], page: int, per_page: int) -> PaginatedProductResponse:
    total = len(items)
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    start = (page - 1) * per_page
    page_items = items[start: start + per_page]

    return PaginatedProductResponse(
        items=[NaverProductItem(**_normalize_item(item)) for item in page_items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


def get_product_products_paginated(
    product: str,
    page: int,
    per_page: int,
) -> PaginatedProductResponse:
    col = get_curated_products_collection()
    docs = list(col.find({"product": product}, {"_id": 0}).sort("productId", 1))
    return _paginate(_dedup_by_product_id(docs), page, per_page)


def get_products_paginated(
    product: str,
    scent_slug: str,
    fragrance_slug: Optional[str],
    page: int,
    per_page: int,
) -> PaginatedProductResponse:
    query = {"product": product, "scent_slug": scent_slug}
    if fragrance_slug:
        query["fragrance_slug"] = fragrance_slug

    col = get_curated_products_collection()
    docs = list(col.find(query, {"_id": 0}).sort("productId", 1))
    return _paginate(_dedup_by_product_id(docs), page, per_page)
