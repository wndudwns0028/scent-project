import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from functools import lru_cache

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

load_dotenv()

DATABASE_NAME = "scent_db"
FRAGRANCE_COLLECTION = "fragrances"
NAVER_CACHE_COLLECTION = "naver_cache"  # 네이버 쇼핑 검색 API 종료(2026-07-31)로 현재 미사용 — curated_product_service 참고
CURATED_PRODUCTS_COLLECTION = "curated_products"
MONGODB_TIMEOUT_MS = 1000
HEALTH_CHECK_TIMEOUT_SECONDS = 1.5


def get_mongodb_url() -> str:
    url = os.getenv("MONGODB_URL")
    if not url:
        raise RuntimeError("MONGODB_URL environment variable is required.")
    return url


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    return MongoClient(
        get_mongodb_url(),
        serverSelectionTimeoutMS=MONGODB_TIMEOUT_MS,
        connectTimeoutMS=MONGODB_TIMEOUT_MS,
        socketTimeoutMS=MONGODB_TIMEOUT_MS,
    )


def get_scent_collection():
    return get_client()[DATABASE_NAME][FRAGRANCE_COLLECTION]


def get_naver_cache_collection():
    return get_client()[DATABASE_NAME][NAVER_CACHE_COLLECTION]


def get_curated_products_collection():
    return get_client()[DATABASE_NAME][CURATED_PRODUCTS_COLLECTION]


def ensure_cache_ttl_index() -> None:
    col = get_naver_cache_collection()
    col.create_index([("cached_at", 1)], expireAfterSeconds=3600, name="ttl_cached_at")
    col.create_index([("cache_key", 1)], unique=True, name="unique_cache_key")


def check_mongodb() -> bool:
    def ping() -> bool:
        get_client().admin.command("ping")
        return True

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return executor.submit(ping).result(timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
    except (RuntimeError, PyMongoError, ServerSelectionTimeoutError, TimeoutError):
        return False
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
