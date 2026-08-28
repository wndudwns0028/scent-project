"""
[미사용/보류] 네이버 쇼핑 검색 API(shop.json)가 2026-07-31부로 종료되어
이 모듈은 더 이상 api/products.py에서 호출되지 않는다.
현재는 services/curated_product_service.py(수동 큐레이션 데이터 기반)가 그 자리를 대체한다.
향후 대체 API를 붙이게 될 경우를 대비해 구조 참고용으로 남겨둔다.
"""

import html as html_module
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import List, Optional

from database.mongodb import get_naver_cache_collection, get_scent_collection
from models.product_schema import NaverProductItem, PaginatedProductResponse
from utils.naver_api import call_naver_shopping_api
from utils.search_constants import FRAGRANCE_SYNONYMS, PRIMARY_PRODUCT_KEYWORD, PRODUCT_KEYWORDS

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", html_module.unescape(text or "")).lower()


def _build_cache_key(product: str, scent_slug: str, fragrance_slug: Optional[str]) -> str:
    if fragrance_slug:
        return f"{product}::{scent_slug}::{fragrance_slug}"
    return f"{product}::{scent_slug}"


def _build_queries(fragrances: list, product: str) -> List[str]:
    """향 당 대표 한국어 동의어 1개 × 대표 제품 키워드 1개"""
    product_keyword = PRIMARY_PRODUCT_KEYWORD.get(product.lower(), product)
    queries = []
    for fragrance in fragrances:
        synonyms = FRAGRANCE_SYNONYMS.get(fragrance["slug"], [])
        term = synonyms[0] if synonyms else fragrance["name"].replace("향", "").strip()
        queries.append(f"{term} {product_keyword}")
    return queries


def _fetch_all(queries: List[str]) -> List[dict]:
    """병렬 Naver API 호출 후 productId 기준 dedup"""
    def fetch_one(query: str) -> List[dict]:
        try:
            result = call_naver_shopping_api(query, display=100)
            return result.get("items", [])
        except Exception as exc:
            logger.warning("Naver API 호출 실패 (query=%s): %s", query, exc)
            return []

    with ThreadPoolExecutor(max_workers=min(len(queries), 5)) as executor:
        results = list(executor.map(fetch_one, queries))

    seen: dict = {}
    for items in results:
        for item in items:
            pid = item.get("productId", "")
            if pid and pid not in seen:
                seen[pid] = item
    return list(seen.values())


def _filter_items(items: List[dict], synonyms: List[str], product_keywords: List[str]) -> List[dict]:
    """title에 향 동의어 AND 제품 키워드 포함 여부로 필터"""
    lower_synonyms = [s.lower() for s in synonyms]
    lower_keywords = [k.lower() for k in product_keywords]

    return [
        item for item in items
        if any(s in _strip_html(item.get("title", "")) for s in lower_synonyms)
        and any(k in _strip_html(item.get("title", "")) for k in lower_keywords)
    ]


def _normalize_item(item: dict) -> dict:
    return {
        "productId": str(item.get("productId", "")),
        "title": item.get("title", ""),
        "link": item.get("link", ""),
        "image": item.get("image", ""),
        "lprice": str(item.get("lprice", "")),
        "mallName": item.get("mallName", ""),
    }


def _get_cached_or_fetch(product: str, scent_slug: str, fragrances: list, cache_col) -> List[dict]:
    """scent 단위 캐시 히트 또는 Naver API 호출"""
    cache_key = _build_cache_key(product, scent_slug, None)
    cached = cache_col.find_one({"cache_key": cache_key}, {"_id": 0, "items": 1})
    if cached:
        return cached["items"]

    queries = _build_queries(fragrances, product)
    raw_items = _fetch_all(queries)

    all_synonyms: List[str] = []
    for f in fragrances:
        syns = FRAGRANCE_SYNONYMS.get(f["slug"], [])
        name = f["name"].replace("향", "").strip()
        all_synonyms.extend(syns if syns else [name])

    product_keywords = PRODUCT_KEYWORDS.get(product.lower(), [product])
    items = _filter_items(raw_items, all_synonyms, product_keywords)

    cache_col.replace_one(
        {"cache_key": cache_key},
        {
            "cache_key": cache_key,
            "product": product,
            "scent_slug": scent_slug,
            "fragrance_slug": None,
            "items": items,
            "total_count": len(items),
            "cached_at": datetime.now(tz=timezone.utc),
        },
        upsert=True,
    )
    logger.info("캐시 저장: %s (%d개)", cache_key, len(items))
    return items


def get_product_products_paginated(
    product: str,
    page: int,
    per_page: int,
) -> PaginatedProductResponse:
    scent_col = get_scent_collection()
    cache_col = get_naver_cache_collection()
    scent_docs = list(scent_col.find({"product": product}, {"_id": 0}))

    if not scent_docs:
        return PaginatedProductResponse(items=[], total=0, page=page, per_page=per_page, total_pages=0)

    seen: dict = {}
    for doc in scent_docs:
        items = _get_cached_or_fetch(product, doc["scent_slug"], doc.get("fragrances", []), cache_col)
        for item in items:
            pid = item.get("productId", "")
            if pid and pid not in seen:
                seen[pid] = item

    all_items = list(seen.values())
    total = len(all_items)
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    start = (page - 1) * per_page
    page_items = all_items[start: start + per_page]

    return PaginatedProductResponse(
        items=[NaverProductItem(**_normalize_item(item)) for item in page_items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


def get_products_paginated(
    product: str,
    scent_slug: str,
    fragrance_slug: Optional[str],
    page: int,
    per_page: int,
) -> PaginatedProductResponse:
    cache_key = _build_cache_key(product, scent_slug, fragrance_slug)
    cache_col = get_naver_cache_collection()

    cached = cache_col.find_one({"cache_key": cache_key}, {"_id": 0, "items": 1, "total_count": 1})
    if cached:
        all_items = cached["items"]
        logger.info("캐시 히트: %s (%d개)", cache_key, len(all_items))
    else:
        logger.info("캐시 미스: %s - Naver API 호출", cache_key)

        scent_col = get_scent_collection()
        doc = scent_col.find_one({"product": product, "scent_slug": scent_slug}, {"_id": 0})
        if not doc:
            return PaginatedProductResponse(items=[], total=0, page=page, per_page=per_page, total_pages=0)

        fragrances = doc.get("fragrances", [])
        if fragrance_slug:
            fragrances = [f for f in fragrances if f["slug"] == fragrance_slug]

        if not fragrances:
            return PaginatedProductResponse(items=[], total=0, page=page, per_page=per_page, total_pages=0)

        queries = _build_queries(fragrances, product)
        raw_items = _fetch_all(queries)

        all_synonyms: List[str] = []
        for f in fragrances:
            syns = FRAGRANCE_SYNONYMS.get(f["slug"], [])
            name = f["name"].replace("향", "").strip()
            all_synonyms.extend(syns if syns else [name])

        product_keywords = PRODUCT_KEYWORDS.get(product.lower(), [product])
        all_items = _filter_items(raw_items, all_synonyms, product_keywords)

        cache_col.replace_one(
            {"cache_key": cache_key},
            {
                "cache_key": cache_key,
                "product": product,
                "scent_slug": scent_slug,
                "fragrance_slug": fragrance_slug,
                "items": all_items,
                "total_count": len(all_items),
                "cached_at": datetime.now(tz=timezone.utc),
            },
            upsert=True,
        )
        logger.info("캐시 저장: %s (%d개)", cache_key, len(all_items))

    total = len(all_items)
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    start = (page - 1) * per_page
    page_items = all_items[start: start + per_page]

    return PaginatedProductResponse(
        items=[NaverProductItem(**_normalize_item(item)) for item in page_items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )
