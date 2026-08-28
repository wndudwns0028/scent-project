import logging
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import products, scent

# from api import naver  # 네이버 쇼핑 검색 API 종료로 미사용 (아래 include_router 주석 참고)
from database.mongodb import check_mongodb, ensure_cache_ttl_index

load_dotenv()
logging.basicConfig(level=logging.INFO)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="Scent Finder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://scent-fe.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scent.router, tags=["Fragrances"])
app.include_router(products.router, tags=["Products"])
# 네이버 쇼핑 검색 API(shop.json)가 2026-07-31부로 종료되어 /naver/search는 항상 502를 반환한다.
# 라우터 파일(api/naver.py)은 참고용으로 남겨두고 앱에는 연결하지 않는다.
# app.include_router(naver.router, prefix="/naver", tags=["Naver"])


@app.on_event("startup")
def startup_event():
    ensure_cache_ttl_index()


@app.get("/health", tags=["Health"])
def health_check():
    mongodb_ok = check_mongodb()
    return {
        "status": "ok" if mongodb_ok else "degraded",
        "mongodb": mongodb_ok,
    }


@app.get("/")
def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/pages/{page_name}.html")
def get_page(page_name: str):
    filepath = os.path.join(STATIC_DIR, "pages", f"{page_name}.html")
    if not os.path.exists(filepath):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"), status_code=404)
    return FileResponse(filepath)


# 정적 애셋 (JS·CSS·이미지) 마운트 — API 라우트 등록 후 마지막에
app.mount("/js", StaticFiles(directory=os.path.join(STATIC_DIR, "js")), name="js")
app.mount("/styles", StaticFiles(directory=os.path.join(STATIC_DIR, "styles")), name="styles")
app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
