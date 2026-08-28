"""
수동으로 채운 CSV(scripts/curated_products_template.csv 형식)를 읽어
`curated_products` 컬렉션에 적재한다.

사용법:
    python scripts/import_curated_products.py [csv_path]
    (csv_path 생략 시 기본값: scripts/curated_products_template.csv)

CSV 컬럼: product, scent_slug, fragrance_slug, productId, title, image, lprice, mallName, link
- productId가 같은 행은 덮어씀 (재실행 안전)
- title/image/lprice/mallName/link 중 하나라도 비어 있으면 건너뜀 (빈 템플릿 행 무시)
"""

import csv
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

REQUIRED_FIELDS = ["product", "scent_slug", "fragrance_slug", "productId", "title", "image", "lprice", "mallName", "link"]

mongodb_url = os.getenv("MONGODB_URL")
if not mongodb_url:
    raise RuntimeError("MONGODB_URL environment variable is required.")

client = MongoClient(mongodb_url, serverSelectionTimeoutMS=3000)
collection = client["scent_db"]["curated_products"]
collection.create_index("productId", unique=True, name="unique_product_id")


def load_rows(csv_path: str) -> list:
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main() -> None:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "curated_products_template.csv"
    )

    rows = load_rows(csv_path)
    inserted, skipped = 0, 0

    for row in rows:
        if not all((row.get(field) or "").strip() for field in REQUIRED_FIELDS):
            skipped += 1
            continue

        doc = {field: row[field].strip() for field in REQUIRED_FIELDS}
        collection.replace_one({"productId": doc["productId"]}, doc, upsert=True)
        inserted += 1

    print(f"적재 완료: {inserted}건, 빈 값으로 건너뜀: {skipped}건 (파일: {csv_path})")


if __name__ == "__main__":
    main()
