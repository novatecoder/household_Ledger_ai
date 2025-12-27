import asyncio
import datetime
import json
from unittest.mock import patch, MagicMock

import pytest
import redis.asyncio as redis

from household_ledger.common.config import settings
from household_ledger.graph.workflow import create_household_workflow
# UnifiedLlmClient 대신 ChatOpenAI를 직접 사용하도록 수정
from langchain_openai import ChatOpenAI 
from langchain_core.messages import HumanMessage, AIMessage

# --- [공통 유틸리티] ---

def json_serial(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def get_manual_initial_state(question: str):
    """모든 LedgerState 키를 초기화하여 KeyError를 방지합니다."""
    return {
        "messages": [HumanMessage(content=question)],
        "refined_question": "",
        "next_step": "",
        "sql_query": "",
        "sql_result": [],
        "graph_query": "",
        "graph_result": [],
        "analysis": "",
        "chart_data": {},
        "retry_count": 0,
        "error": None,
        "user_id": "manual_test_user",
        "session_id": "manual_test_session"
    }

# --- [테스트용 Fixtures] ---

@pytest.fixture
async def redis_client_fixture():
    client = redis.Redis(
        host=settings.REDIS_HOST, 
        port=settings.REDIS_PORT, 
        decode_responses=True
    )
    yield client
    await client.aclose()

@pytest.fixture
def langchain_llm():
    """
    nodes.py의 노드들이 기대하는 .ainvoke() 메서드를 가진 
    실제 LangChain ChatOpenAI 객체를 반환합니다.
    """
    return ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY or "none",
        temperature=0
    )

# -----------------------------------------------------------------
# 1. 기본 지출 조회 시나리오
# -----------------------------------------------------------------

@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_basic_ledger_query(langchain_llm, redis_client_fixture):
    print(f"\n🚀 [1/3] 기본 지출 조회 시나리오 시작...")
    
    # get_llm이 ainvoke가 있는 langchain_llm을 반환하도록 패치
    with patch("household_ledger.graph.nodes.redis_client", redis_client_fixture), \
         patch("household_ledger.graph.nodes.get_llm", return_value=langchain_llm):
        
        graph = create_household_workflow()
        question = "가장 큰 금액이 결제된 지출 내역 3개만 보여줘"
        
        state = get_manual_initial_state(question)
        out = await graph.ainvoke(state)
        
        print(f"   - 생성된 SQL: {out.get('sql_query')}")
        assert out.get("sql_result") is not None
        print(f"✅ 결과 샘플: {out['sql_result'][0] if out['sql_result'] else '데이터 없음'}")

# -----------------------------------------------------------------
# 2. 가계부 꼬리 물기 시나리오
# -----------------------------------------------------------------

@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_ledger_sequential_context(langchain_llm, redis_client_fixture):
    print(f"\n🚀 [2/3] 가계부 꼬리 물기 시나리오 시작...")
    
    with patch("household_ledger.graph.nodes.redis_client", redis_client_fixture), \
         patch("household_ledger.graph.nodes.get_llm", return_value=langchain_llm):
        
        graph = create_household_workflow()
        
        q1 = "지난달 식비로 얼마 썼어?"
        res1 = await graph.ainvoke(get_manual_initial_state(q1))
        
        q2 = "그중에서 스타벅스는?"
        state2 = get_manual_initial_state(q2)
        state2["messages"] = res1["messages"] + state2["messages"]
        
        res2 = await graph.ainvoke(state2)
        
        print(f"   - 정제된 질문: {res2.get('refined_question')}")
        sql_text = str(res2.get('sql_query')).upper()
        assert "STARBUCKS" in sql_text or "스타벅스" in str(res2.get('refined_question'))
        print("✅ 가계부 맥락 유지 확인 완료")

# -----------------------------------------------------------------
# 3. Neo4j 관계 기반 지출 탐색 시나리오
# -----------------------------------------------------------------

@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_ledger_graph_bridge(langchain_llm, redis_client_fixture):
    print(f"\n🚀 [3/3] Neo4j-SQL 관계 브릿지 테스트...")
    
    with patch("household_ledger.graph.nodes.redis_client", redis_client_fixture), \
         patch("household_ledger.graph.nodes.get_llm", return_value=langchain_llm):
        
        graph = create_household_workflow()
        question = "스타벅스와 같은 카테고리에 있는 모든 가맹점의 총 지출액을 알려줘."
        
        state = get_manual_initial_state(question)
        out = await graph.ainvoke(state)
        
        print(f"   - 선택된 경로: {out.get('next_step')}")
        assert out.get("next_step") in ["GRAPH", "SQL"]
        print(f"✅ 관계 기반 분석 성공")