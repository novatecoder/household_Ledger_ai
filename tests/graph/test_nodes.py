import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from household_ledger.graph.nodes import (
    validate_sql_security,
    get_dynamic_schema_info,
    check_cache_logic,
    query_refiner_node,
    intent_router_node,
    sql_generator_node,
    validate_sql_logic,
    execute_sql_logic,
    final_analyzer_node
)

# --- [1. 유틸리티 테스트] ---

def test_sql_security_guard():
    assert validate_sql_security("SELECT amount FROM transactions") is True
    assert validate_sql_security("DROP TABLE accounts") is False
    assert validate_sql_security("DELETE FROM transactions") is False

def test_dynamic_schema_extraction():
    schema = get_dynamic_schema_info()
    assert "Table: accounts" in schema
    assert "Table: transactions" in schema

# --- [2. 노드 로직 테스트] ---

@pytest.mark.asyncio
async def test_check_cache_logic_hit():
    # state 구성 (마지막 메시지 기준 캐시 키 생성 대응)
    state = {"user_id": "u1", "messages": [MagicMock(content="식비 내역")]}
    cached_data = [{"amount": 1000}]
    
    with patch("household_ledger.graph.nodes.redis_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = json.dumps(cached_data)
        res = await check_cache_logic(state)
        assert res["is_cached"] is True
        assert res["sql_result"] == cached_data

@pytest.mark.asyncio
async def test_query_refiner_node_logic():
    state = {"messages": [MagicMock(content="지난달 식비"), MagicMock(content="스타벅스는?")]}
    
    with patch("household_ledger.graph.nodes.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="지난달 스타벅스 지출 내역은?")
        mock_get_llm.return_value = mock_llm
        
        res = await query_refiner_node(state)
        assert res["refined_question"] == "지난달 스타벅스 지출 내역은?"

@pytest.mark.asyncio
async def test_intent_router_node_logic():
    state = {"refined_question": "식비 분석해줘"}
    
    with patch("household_ledger.graph.nodes.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        # nodes.py의 json.loads(res.content)["intent"] 로직 대응
        mock_llm.ainvoke.return_value = MagicMock(content=json.dumps({"intent": "SQL"}))
        mock_get_llm.return_value = mock_llm
        
        res = await intent_router_node(state)
        assert res["next_step"] == "SQL"

@pytest.mark.asyncio
async def test_execute_sql_logic_with_serialization():
    """Decimal 결과가 JSON 직렬화 가능하도록 변환되는지 테스트"""
    from decimal import Decimal
    state = {"sql_query": "SELECT amount FROM transactions", "error": None}
    
    with patch("household_ledger.graph.nodes.sql_engine.connect") as mock_connect:
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_result = mock_conn.execute.return_value
        
        # SQLAlchemy Row Mapping 모사
        mock_row = MagicMock()
        mock_row._mapping = {"amount": Decimal("5000.0")}
        mock_result.__iter__.return_value = [mock_row]
        
        res = await execute_sql_logic(state)
        # nodes.py 내부의 pd.Series 직렬화 로직 통과 확인
        assert res["sql_result"][0]["amount"] == 5000.0
        assert isinstance(res["sql_result"][0]["amount"], (float, int))

@pytest.mark.asyncio
async def test_final_analyzer_node_with_chart():
    state = {"sql_result": [{"amount": 5000}], "refined_question": "질문"}
    
    with patch("household_ledger.graph.nodes.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="분석 결과입니다. [CHART_JSON] {\"type\":\"pie\"}")
        mock_get_llm.return_value = mock_llm
        
        res = await final_analyzer_node(state)
        assert "분석 결과입니다" in res["analysis"]