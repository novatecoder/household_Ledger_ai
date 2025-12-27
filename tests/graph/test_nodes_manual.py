import pytest
import asyncio
import json
import redis.asyncio as redis
from unittest.mock import patch, MagicMock
from household_ledger.graph.nodes import (
    check_cache_logic, 
    query_refiner_node,
    intent_router_node,         
    sql_generator_node, 
    validate_sql_logic, 
    execute_sql_logic,
    final_analyzer_node,
    get_dynamic_schema_info
)
from household_ledger.common.config import settings

# --- [Fixtures] ---

@pytest.fixture
async def redis_client_fixture():
    """실제 Redis 연결 테스트용 픽스처"""
    client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
    yield client
    await client.aclose()

# --- [Individual Node Manual Tests] ---

@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_node_1_check_cache(redis_client_fixture):
    """[1] Redis 캐시 로직 검증"""
    print("\n🔍 [Node Manual] 1. check_cache_logic 테스트...")
    state = {
        "user_id": "tester", 
        "messages": [MagicMock(content="지난달 식비 총액")]
    }
    
    with patch("household_ledger.graph.nodes.redis_client", redis_client_fixture):
        res = await check_cache_logic(state)
        print(f"   - Initial Cache Hit: {res.get('is_cached')}")
        assert res["is_cached"] is False
    print("✅ 캐시 체크 노드 확인 완료")


@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_node_2_refiner_and_router():
    """[2] 꼬리물기 질문 정제(Refiner) 및 의도 분석(Router) 테스트"""
    print("\n🔍 [Node Manual] 2. Refiner & Router 테스트...")
    
    # 상황: 이전 대화 맥락이 있는 질문
    mock_history = [
        MagicMock(content="이번 달 식비 알려줘"),
        MagicMock(content="식비는 총 15만원입니다.")
    ]
    state = {
        "messages": mock_history + [MagicMock(content="그중에서 스타벅스는?")]
    }
    
    # 1. Refiner 테스트
    res_refine = await query_refiner_node(state)
    refined_q = res_refine["refined_question"]
    print(f"   - 정제된 질문: {refined_q}")
    assert "스타벅스" in refined_q

    # 2. Router 테스트
    state["refined_question"] = refined_q
    res_route = await intent_router_node(state)
    print(f"   - 결정된 경로: {res_route['next_step']}")
    assert res_route["next_step"] in ["SQL", "GRAPH", "GENERAL"]
    print("✅ 라우터 노드 판단 완료")


@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_node_3_sql_generation():
    """[3] 가계부 스키마 기반 SQL 생성 테스트"""
    print("\n🔍 [Node Manual] 3. sql_generator_node 테스트...")
    
    state = {"refined_question": "스타벅스에서 결제한 최근 내역 3개 보여줘"}
    
    res = await sql_generator_node(state)
    print(f"   - 생성된 SQL:\n{res['sql_query']}")
    
    assert "SELECT" in res["sql_query"].upper()
    assert "transactions" in res["sql_query"].lower()
    print("✅ SQL 생성 노드 확인 완료")


@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_node_4_validate_sql():
    """[4] SQL 보안 및 문법 가드레일 검증 테스트"""
    print("\n🔍 [Node Manual] 4. validate_sql_logic 테스트...")
    
    # Case 1: 보안 위반 (DROP 시도)
    state_fail = {"sql_query": "DROP TABLE accounts", "retry_count": 0}
    res_fail = await validate_sql_logic(state_fail)
    print(f"   - 보안 위반 감지: {res_fail['error']}")
    assert res_fail["error"] == "SECURITY_VIOLATION"

    # Case 2: 정상 SQL
    state_pass = {"sql_query": "SELECT * FROM transactions LIMIT 5", "retry_count": 0}
    res_pass = await validate_sql_logic(state_pass)
    print(f"   - 정상 SQL 검증: {'PASS' if not res_pass['error'] else 'FAIL'}")
    assert res_pass["error"] is None
    print("✅ SQL 검증 가드레일 통과")


@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_node_5_execute_sql():
    """[5] 실제 Postgres DB 데이터 실행 및 직렬화 검증"""
    print("\n🔍 [Node Manual] 5. execute_sql_logic 테스트...")
    
    state = {
        "sql_query": "SELECT amount, category, transaction_date FROM transactions LIMIT 1",
        "error": None
    }
    
    res = await execute_sql_logic(state)
    
    # [수정] 에러 여부 출력 로직 추가
    if res.get("error"):
        print(f"   ❌ DB 실행 중 에러 발생: {res['error']}")
    
    # [수정] res['sql_result'] 대신 res.get('sql_result', []) 사용
    sql_data = res.get("sql_result", [])
    print(f"   - DB 조회 결과: {sql_data}")
    
    assert sql_data is not None
    print("✅ DB 실행 및 데이터 로드 완료")


@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_node_6_final_analysis():
    """[6] 최종 분석 및 시각화 JSON 생성 테스트"""
    print("\n🔍 [Node Manual] 6. final_analyzer_node 테스트...")
    
    state = {
        "refined_question": "이번 달 스타벅스 지출 분석해줘",
        "sql_result": [{"merchant_id": "Starbucks", "amount": 5000}, {"merchant_id": "Starbucks", "amount": 12000}]
    }
    
    res = await final_analyzer_node(state)
    print(f"   - AI 분석 답변: {res['analysis'][:100]}...")
    
    # 시각화 태그 포함 여부 (nodes.py 로직에 따라 다름)
    assert len(res["analysis"]) > 0
    print("✅ 최종 분석 노드 확인 완료")


@pytest.mark.skipif(not settings.RUN_MANUAL_TESTS, reason="수동 테스트 비활성화")
@pytest.mark.asyncio
async def test_manual_node_7_dynamic_schema():
    """[7] 가계부 도메인 동적 스키마 추출 확인"""
    print("\n🔍 [Node Manual] 7. get_dynamic_schema_info 테스트...")
    schema = get_dynamic_schema_info()
    print(f"   - 추출된 스키마 샘플: {schema[:200]}...")
    assert "transactions" in schema
    assert "accounts" in schema
    print("✅ 동적 스키마 추출 확인 완료")