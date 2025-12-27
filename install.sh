#!/bin/bash

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}============================================================${NC}"
echo -e "${YELLOW}       💰 Household Ledger AI 설치 및 환경 구성 시작         ${NC}"
echo -e "${CYAN}============================================================${NC}"

echo -e "\n${BLUE}==> [1/5] 로컬 개발 환경 의존성 설치 (Poetry)${NC}"
poetry install

if [ ! -f .env ]; then
    echo -e "${BLUE}==> [2/5] 환경 변수 설정 (.env.sample -> .env)${NC}"
    # .env.sample이 없는 경우를 대비해 예외 처리를 추가하면 좋습니다.
    if [ -f .env.sample ]; then
        cp .env.sample .env
        echo -e "${GREEN}✔ .env 파일이 생성되었습니다. 필요한 API Key를 확인해주세요.${NC}"
    else
        echo -e "${YELLOW}⚠ .env.sample 파일을 찾을 수 없어 .env 생성을 건너뜁니다.${NC}"
    fi
fi

echo -e "${BLUE}==> [3/5] Docker 인프라 기동 및 이미지 빌드${NC}"
echo -e "${CYAN}(Postgres, Redis, Neo4j, vLLM, API, Dashboard)${NC}"
# --build 옵션으로 수정된 소스 코드를 Docker 이미지에 즉시 반영
docker compose up -d --build

echo -e "${BLUE}==> 서비스 안정화 및 모델 로딩 대기 (60초)...${NC}"
# vLLM 모델 로딩 시간을 고려하여 대기 시간을 조금 더 늘렸습니다.
sleep 60

echo -e "${BLUE}==> [4/5] 데이터베이스 초기화 및 가계부 데이터 적재${NC}"
# pyproject.toml의 scripts 항목이 ledger-drop, ledger-ingest로 되어 있다고 가정합니다.
echo "y" | poetry run ledger-drop
poetry run ledger-ingest

echo -e "\n${GREEN}==> [5/5] 모든 설정이 완료되었습니다!${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"
echo -e "${GREEN}🚀 [가계부 AI 대시보드]${NC}"
echo -e "${GREEN}👉 URL: http://localhost:8501${NC}"
echo -e ""
echo -e "${CYAN}📚 [백엔드 API 문서]${NC}"
echo -e "${CYAN}👉 Swagger UI: http://localhost:8001/docs${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"
echo -e "${YELLOW}📊 [인프라 관리 포트]${NC}"
echo -e "${BLUE}• DB Admin (Adminer):    http://localhost:8080${NC}"
echo -e "${BLUE}• Graph DB (Neo4j):      http://localhost:7474${NC}"
echo -e "${BLUE}• Inference (vLLM):      http://localhost:8000/v1${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"