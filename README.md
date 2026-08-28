# Scent Finder

향수·뷰티 제품의 향 카테고리를 탐색하고 네이버 쇼핑에서 관련 상품을 연결하는 중개 서비스입니다.

## 서비스 개요

- 제품 유형(향수, 바디로션 등) → 향 계열(플로럴, 우디 등) → 세부 향(장미, 샌달우드 등) 순으로 드릴다운 탐색
- 선택한 향에 맞춰 수동으로 큐레이션한 상품 데이터를 카드 형태로 표시 (~~네이버 쇼핑 검색~~ 2026-07-31 서비스 종료로 중단, 상세는 [`docs/프로젝트-개발-기록.md`](docs/프로젝트-개발-기록.md) 참고)
- 직접 판매 없이 탐색·중개에 집중

## 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | Python, FastAPI, MongoDB (Motor), Uvicorn |
| 프론트엔드 | HTML, CSS, Vanilla JS (빌드 도구 없음) |
| 상품 데이터 | 수동 큐레이션 (CSV → MongoDB `curated_products` 컬렉션) — ~~네이버 쇼핑 검색 API~~ (종료됨) |
| 서빙 방식 | FastAPI StaticFiles — 단일 서버에서 API + 프론트엔드 동시 서빙 |

## 프로젝트 구조

```
test_project_v1/
├── fragrance-be/          # FastAPI 백엔드 (프론트엔드도 함께 서빙)
│   ├── main.py            # 앱 진입점 — 라우터 등록 + StaticFiles 마운트
│   ├── api/               # 라우터 핸들러 (얇게 유지)
│   │   ├── scent.py       # 향 카테고리 API
│   │   ├── products.py    # 상품 관련 API (curated_product_service 사용)
│   │   └── naver.py       # (미사용/보류) 네이버 쇼핑 검색 API — 종료로 앱에 미연결
│   ├── services/          # 비즈니스 로직
│   │   ├── curated_product_service.py  # 현재 사용 — 큐레이션 데이터 조회
│   │   └── product_service.py          # (미사용/보류) 네이버 검색 기반 로직
│   ├── utils/             # 외부 API 호출 (naver_api.py, 현재 미사용)
│   ├── database/          # MongoDB 연결 (lru_cache 싱글톤)
│   ├── models/            # Pydantic 스키마
│   ├── scripts/           # 데이터 입력 스크립트
│   │   ├── seed_data.py                     # 향 카테고리 초기 데이터
│   │   ├── curated_products_template.csv    # 큐레이션 상품 데이터 입력 양식
│   │   └── import_curated_products.py       # CSV → MongoDB 적재
│   ├── static/            # 프론트엔드 정적 파일
│   │   ├── index.html
│   │   ├── pages/         # fragrance.html, product.html, scent.html
│   │   ├── js/            # shared.js + 페이지별 JS
│   │   ├── styles/
│   │   └── assets/
│   ├── requirements.txt
│   └── .env.template      # 환경 변수 양식 (실제 값 없음)
├── new_fe/                # (레거시) 더 이상 사용하지 않음
└── docs/                  # 프로젝트 문서
    └── 프로젝트-개발-기록.md
```

## 로컬 실행

### 사전 요구사항

- Python 3.x
- MongoDB 실행 중 (기본 포트 27017, 또는 Atlas 등 클라우드 연결 문자열)

### 초기 세팅 (Windows)

```powershell
cd fragrance-be

# 가상 환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate

# 의존성 설치
python -m pip install -r requirements.txt

# 환경 변수 설정
copy .env.template .env
# .env 파일을 열어 MongoDB URL 입력

# 초기 향 카테고리 데이터 입력
python scripts/seed_data.py

# 큐레이션 상품 데이터 입력 (scripts/curated_products_template.csv 를 채운 뒤)
python scripts/import_curated_products.py

# 서버 실행
uvicorn main:app --reload
```

### 초기 세팅 (Linux / Mac)

```bash
cd fragrance-be
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
# .env 파일 편집 후 MongoDB URL 입력
python scripts/seed_data.py
python scripts/import_curated_products.py
uvicorn main:app --reload
```

서버 실행 후 `http://127.0.0.1:8000` 에서 프론트엔드와 API 모두 접근 가능합니다.

## 환경 변수

`fragrance-be/.env.template` 을 복사해 `.env` 를 만들고 아래 값을 입력합니다.

```env
MONGODB_URL=mongodb://localhost:27017
NAVER_CLIENT_ID=발급받은_클라이언트_ID   # 네이버 쇼핑 검색 API 종료로 현재 미사용
NAVER_CLIENT_SECRET=발급받은_클라이언트_시크릿  # 네이버 쇼핑 검색 API 종료로 현재 미사용
```

> `.env` 파일은 `.gitignore` 에 의해 Git에서 제외됩니다. 절대 커밋하지 마세요.

## 주요 API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 메인 페이지 |
| GET | `/pages/{name}.html` | 서브 페이지 |
| GET | `/fragrances` | 향 카테고리 목록 |
| GET | `/fragrances/{product}/products` | 제품 전체 향 상품 목록 (페이지네이션) |
| GET | `/fragrances/{product}/{scent_slug}/products` | 향 계열별 상품 목록 (페이지네이션) |
| ~~GET~~ | ~~`/naver/search?query=&display=`~~ | (미사용) 네이버 쇼핑 검색 종료로 라우터 비활성화 |
| GET | `/health` | 서버 및 MongoDB 상태 확인 |

API 문서: `http://127.0.0.1:8000/docs`

## 개발 로드맵

- **Phase 1 (단기)**: 큐레이션 상품 데이터 채우기 (14개 조합 × 3~5개 상품), 가격 주기적 갱신 루틴
- **Phase 2 (중기)**: 서비스 완성 — 상품 카드 디자인 고도화, 향 데이터 확장
- **Phase 3 (장기)**: 커뮤니티 기능 + 프론트엔드 Next.js 전환

자세한 내용은 [`docs/프로젝트-개발-기록.md`](docs/프로젝트-개발-기록.md) 를 참고하세요.
