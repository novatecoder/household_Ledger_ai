import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from household_ledger.graph.workflow import create_household_workflow, display_graph_info

# --- [Fixtures: 공통 모킹 객체] ---

@pytest.fixture
def mock_llm():
    """nodes.py의 로직(res.content)을 따르는 비동기 LLM 모킹"""
    mock = AsyncMock()
    def create_response(content):
        m = MagicMock()
        m.content = content
        return m
    mock.create_response = create_response
    return mock

def get_full_state(messages=None):
    """LedgerState의 모든 키를 초기화하여 KeyError 및 데이터 유실 방지"""
    return {
        "messages": messages or [],
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
        "user_id": "test_user",
        "session_id": "test_session"
    }

# -----------------------------------------------------------------
# 1. SQL 경로 테스트: 리트라이 루프 (FAIL -> PASS)
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_sql_path_with_retry(mock_llm):
    """
    [Scenario] 단발성 질문 (Refiner LLM 호출 없음)
    Router(SQL) -> sql_gen(1차) -> validate(FAIL) -> sql_gen(2차) -> validate(PASS)
    """
    # 호출 순서: 1.router, 2.sql_gen(1), 3.validate(FAIL), 4.sql_gen(2), 5.validate(PASS), 6.analyzer
    mock_llm.ainvoke.side_effect = [
        mock_llm.create_response('{"intent": "SQL"}'),             # 1. router
        mock_llm.create_response("SELECT * FROM wrong"),           # 2. sql_gen (1차)
        mock_llm.create_response("FAIL"),                          # 3. validate (retry_count -> 1)
        mock_llm.create_response("SELECT sum(amount) FROM trans"), # 4. sql_gen (2차)
        mock_llm.create_response("PASS"),                          # 5. validate (성공)
        mock_llm.create_response("합계는 5만원입니다. [CHART_JSON] {}") # 6. analyzer
    ]

    with patch("household_ledger.graph.nodes.get_llm", return_value=mock_llm), \
         patch("household_ledger.graph.nodes.redis_client", new_callable=AsyncMock), \
         patch("household_ledger.graph.nodes.sql_engine.connect") as mock_connect:
        
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.__iter__.return_value = [MagicMock(_mapping={"sum": 50000})]
        
        graph = create_household_workflow()
        # 메시지가 하나이므로 Refiner는 LLM을 부르지 않고 원문을 refined_question으로 사용함
        initial_state = get_full_state(messages=[HumanMessage(content="식비 얼마야?")])
        
        final_state = await graph.ainvoke(initial_state)
        
        assert final_state["next_step"] == "SQL"
        assert final_state["retry_count"] == 1
        assert "5만원" in final_state["analysis"]

# -----------------------------------------------------------------
# 2. GRAPH 경로 테스트: 연속 질문 (Refiner 호출 포함)
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_graph_multi_turn(mock_llm):
    """
    [Scenario] 연속 질문 (Refiner LLM 호출 있음)
    Refiner -> Router(GRAPH) -> graph_gen -> executor -> analyzer
    """
    # 호출 순서: 1.refiner, 2.router, 3.graph_gen, 4.analyzer
    mock_llm.ainvoke.side_effect = [
        mock_llm.create_response("식비 중 스타벅스 지출 내역"),      # 1. refiner 호출됨
        mock_llm.create_response('{"intent": "GRAPH"}'),          # 2. router
        mock_llm.create_response("MATCH (n:Merchant)..."),        # 3. graph_gen
        mock_llm.create_response("분석 결과입니다.")                # 4. analyzer
    ]

    with patch("household_ledger.graph.nodes.get_llm", return_value=mock_llm), \
         patch("household_ledger.graph.nodes.redis_client", new_callable=AsyncMock), \
         patch("household_ledger.graph.nodes.GraphDatabase.driver") as mock_driver:
        
        mock_session = mock_driver.return_value.session.return_value.__enter__.return_value
        mock_session.run.return_value = [{"count": 10}]
        
        graph = create_household_workflow()
        # 대화 기록(history)이 있으므로 Refiner가 LLM을 호출함
        state = get_full_state(messages=[
            HumanMessage(content="지난달 소비 알려줘"),
            AIMessage(content="총 100만원입니다."),
            HumanMessage(content="그중 스타벅스는?")
        ])
        
        result = await graph.ainvoke(state)
        
        assert result["refined_question"] == "식비 중 스타벅스 지출 내역"
        assert result["next_step"] == "GRAPH"

# -----------------------------------------------------------------
# 3. GENERAL 경로 테스트: 일반 대화
# -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_general_path(mock_llm):
    """
    [Scenario] 일반 대화 (Router -> Analyzer)
    """
    # 호출 순서: 1.router, 2.analyzer
    mock_llm.ainvoke.side_effect = [
        mock_llm.create_response('{"intent": "GENERAL"}'),      # 1. router
        mock_llm.create_response("안녕하세요! 가계부 도우미입니다.")   # 2. analyzer
    ]

    with patch("household_ledger.graph.nodes.get_llm", return_value=mock_llm), \
         patch("household_ledger.graph.nodes.redis_client", new_callable=AsyncMock) as mock_redis:
        
        graph = create_household_workflow()
        state = get_full_state(messages=[HumanMessage(content="안녕")])
        
        result = await graph.ainvoke(state)
        
        assert result["next_step"] == "GENERAL"
        assert result["sql_query"] == ""  # Executor를 타지 않음
        assert mock_redis.lpush.called    # 대화 내역 저장은 수행함

# -----------------------------------------------------------------
# 4. 워크플로우 구조 및 시각화 테스트
# -----------------------------------------------------------------

def test_workflow_structure_verification():
    """워크플로우 노드 등록 여부 확인"""
    graph = create_household_workflow()
    display_graph_info(graph)
    
    nodes = graph.get_graph().nodes
    # 핵심 노드들이 정상적으로 그래프에 포함되었는지 확인
    assert all(k in nodes for k in ["refiner", "router", "executor", "analyzer", "save_history"])