FROM python:3.12-slim

# 1. 환경 변수 설정
# PYTHONPATH에 /app/src를 추가하여 household_ledger 패키지를 찾을 수 있게 합니다.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONPATH=/app/src

# 2. 시스템 의존성 설치
# PostgreSQL 연결을 위한 libpq-dev 및 컴파일 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. Poetry 설치
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# 4. 의존성 파일 복사 및 설치 (캐싱 활용)
COPY pyproject.toml poetry.lock* ./
# --no-root 옵션으로 라이브러리만 먼저 설치하여 빌드 속도를 높입니다.
RUN poetry install --no-interaction --no-ansi --no-root

# 5. 소스 코드 전체 복사
COPY . .

# 6. 현재 프로젝트를 패키지로 설치
# 이 단계에서 src 안의 household_ledger가 파이썬 환경에 등록됩니다.
RUN poetry install --no-interaction --no-ansi

# 7. 포트 노출 (백엔드 8001, 프론트엔드 8501 모두 대비)
EXPOSE 8001
EXPOSE 8501

# 기본 명령어: FastAPI 서버 실행 (가계부 경로로 수정됨)
# docker-compose.yml에서 command를 통해 streamlit 실행으로 변경 가능합니다.
CMD ["uvicorn", "household_ledger.main:app", "--host", "0.0.0.0", "--port", "8001"]