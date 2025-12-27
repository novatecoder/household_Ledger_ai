import asyncio
import json
import logging
from typing import List, Dict, Any, Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from household_ledger.graph.workflow import create_household_workflow
from household_ledger.common.config import settings

# 로그 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Household Ledger AI API",
    description="가계부 지출 분석 및 소비 패턴 진단을 위한 지능형 에이전트 서비스"
)

# 1. 워크플로우 그래프 초기화 (가계부 전용)
# 이제 인자 없이 호출하도록 설계된 워크플로우를 사용합니다.
graph = create_household_workflow()

# 2. Redis 클라이언트 초기화
redis_client = redis.Redis(
    host=settings.REDIS_HOST, 
    port=settings.REDIS_PORT, 
    decode_responses=True
)

# --- [SECTION: Pydantic 모델] ---

class AnalyzeRequest(BaseModel):
    user_id: str = Field(..., examples=["kwh_01"])
    session_id: str = Field(..., examples=["sess_20251228"])
    question: str = Field(..., examples=["이번 달 식비가 가장 많이 나간 날은 언제야?"])

class SaveManualRequest(BaseModel):
    """분석 결과를 수동으로 별도 저장하고 싶을 때 사용 (선택 사항)"""
    user_id: str
    question: str
    analysis: str
    chart_data: Dict[str, Any]

# --- [SECTION: API 엔드포인트] ---

@app.post("/api/v1/analyze")
async def analyze_ledger(req: AnalyzeRequest):
    """
    사용자의 질문을 받아 가계부 분석 워크플로우를 실행합니다.
    Refiner -> Router -> SQL/Graph -> Executor -> Analyzer -> Save 순으로 진행됩니다.
    """
    # [핵심] LedgerState 구조와 정확히 일치하도록 초기 상태 구성
    initial_state = {
        "messages": [HumanMessage(content=req.question)],
        "refined_question": "",
        "next_step": "",
        "retry_count": 0,
        "error": None,
        "sql_query": "",
        "sql_result": [],
        "graph_query": "",
        "graph_result": [],
        "analysis": "",
        "chart_data": {},
        "user_id": req.user_id,
        "session_id": req.session_id
    }
    
    try:
        # LangGraph 비동기 실행
        final_state = await graph.ainvoke(initial_state)
        
        # 워크플로우 내부 로직 에러 체크
        if final_state.get("error") and not final_state.get("analysis"):
            logger.error(f"Workflow Error: {final_state['error']}")
            raise HTTPException(status_code=400, detail=final_state["error"])

        # 최종 응답 반환
        return {
            "refined_question": final_state.get("refined_question"),
            "next_step": final_state.get("next_step"),
            "sql_query": final_state.get("sql_query"),
            "analysis": final_state.get("analysis"),
            "chart_data": final_state.get("chart_data"),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Critical System Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {str(e)}")

@app.post("/api/v1/save-manual")
async def save_manual_cache(req: SaveManualRequest):
    """
    분석 결과를 Redis에 5분간 강제 캐싱합니다.
    (이미 워크플로우 마지막 노드에서 자동 저장되지만, 별도 API가 필요한 경우 사용)
    """
    cache_key = f"manual_cache:{req.user_id}:{hash(req.question)}"
    try:
        data = {
            "analysis": req.analysis,
            "chart_data": req.chart_data
        }
        await redis_client.setex(cache_key, 300, json.dumps(data))
        return {"message": "수동 저장 완료", "key": cache_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis 저장 오류: {str(e)}")

@app.get("/health")
async def health_check():
    """서버 상태 및 LLM 모델 정보 확인"""
    return {
        "status": "healthy", 
        "project": "Household Ledger AI",
        "model": settings.LLM_MODEL_NAME
    }

if __name__ == "__main__":
    import uvicorn
    # 8001 포트로 API 서버 실행
    uvicorn.run(app, host="0.0.0.0", port=8001)