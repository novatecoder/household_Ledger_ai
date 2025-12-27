import json
import re
import logging
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI
from household_ledger.graph.state import LedgerState
from household_ledger.common.config import settings
from household_ledger.domain import models
import redis.asyncio as redis

# 로깅 및 DB 엔진 설정
logger = logging.getLogger(__name__)
sql_engine = create_engine(f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)

# --- [Utility Functions] ---

def get_llm():
    """LLM 객체를 지연 로딩하여 테스트 수집 시 api_key 에러를 방지합니다."""
    return ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY or "none",
        temperature=0
    )

def get_dynamic_schema_info() -> str:
    """SQLAlchemy 모델에서 가계부 테이블 정보를 동적으로 추출합니다."""
    schema_info = []
    for name, obj in vars(models).items():
        if isinstance(obj, type) and hasattr(obj, "__tablename__") and obj != models.Base:
            inst = inspect(obj)
            columns = [f"- {col.name} ({col.type})" for col in inst.columns]
            schema_info.append(f"Table: {obj.__tablename__}\nColumns:\n" + "\n".join(columns))
    return "\n\n".join(schema_info)

def validate_sql_security(sql: str) -> bool:
    """SQL Injection 및 파괴적인 명령어를 방어합니다."""
    forbidden = [r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b", r"\bTRUNCATE\b", r"\bALTER\b"]
    sql_upper = sql.upper()
    for pattern in forbidden:
        if re.search(pattern, sql_upper):
            return False
    return sql_upper.strip().startswith("SELECT")

# --- [Workflow Nodes] ---

async def check_cache_logic(state: LedgerState):
    """Redis 캐시를 확인합니다."""
    cache_key = f"ledger_cache:{state.get('user_id')}:{state['messages'][-1].content.strip()}"
    cached = await redis_client.get(cache_key)
    if cached:
        return {"is_cached": True, "sql_result": json.loads(cached)}
    return {"is_cached": False}

async def query_refiner_node(state: LedgerState):
    """꼬리물기 질문을 독립적인 질문으로 정제합니다."""
    llm = get_llm()
    history = state.get("messages", [])[:-1]
    current_q = state["messages"][-1].content
    if not history: return {"refined_question": current_q}

    prompt = f"이전 대화: {history[-3:]}\n현재 질문: {current_q}\n위 맥락을 반영한 완성된 질문 하나만 작성하세요."
    res = await llm.ainvoke(prompt)
    return {"refined_question": res.content}

async def intent_router_node(state: LedgerState):
    """질문 의도 분석 및 경로 결정 (Few-shot 가이드 추가)"""
    llm = get_llm()
    
    # 프롬프트에 구체적인 가이드와 예시를 추가합니다.
    prompt = f"""당신은 가계부 에이전트의 경로 결정자입니다. 
질문을 분석하여 [SQL, GRAPH, GENERAL] 중 하나로 분류하세요.

- SQL: 지출 합계, 평균, 특정 기간 내역 조회 등 숫자 계산이 필요한 경우
  (예: "이번 달 식비 얼마야?", "가장 많이 쓴 곳 3개 보여줘")
- GRAPH: 가맹점 간의 관계, 카테고리별 패턴, 유사 사용자 분석 등 관계 중심인 경우
  (예: "스타벅스와 같은 카테고리인 곳들 알려줘", "내 소비 패턴이랑 비슷한 가맹점은?")
- GENERAL: 인사, 도움말, 가계부 팁 등 데이터 조회가 필요 없는 일반 대화
  (예: "안녕", "가계부 잘 쓰는 법 알려줘")

질문: {state['refined_question']}

반드시 아래 JSON 형식으로만 응답하세요:
{{"intent": "SQL 또는 GRAPH 또는 GENERAL"}}
"""
    
    res = await llm.ainvoke(prompt)
    content = res.content
    
    # (이전과 동일한 파싱 로직)
    import re
    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            intent = json.loads(match.group())["intent"]
        else:
            content_upper = content.upper()
            if "GRAPH" in content_upper: intent = "GRAPH"
            elif "SQL" in content_upper: intent = "SQL"
            else: intent = "GENERAL"
    except:
        intent = "GENERAL"

    # 허용된 키워드 외에는 GENERAL로 강제
    if intent not in ["SQL", "GRAPH", "GENERAL"]:
        intent = "GENERAL"
        
    return {"next_step": intent}

async def sql_generator_node(state: LedgerState):
    """가계부 SQL 생성."""
    llm = get_llm()
    schema = get_dynamic_schema_info()
    
    # [수정] SQL 키워드 간 공백을 강제하고 가독성을 높이도록 프롬프트 강화
    prompt = f"""가계부 데이터베이스를 조회하기 위한 PostgreSQL 쿼리를 작성하세요.
스키마:
{schema}

질문: {state['refined_question']}

주의사항:
1. 반드시 SQL 키워드(SELECT, FROM, WHERE, ORDER BY, LIMIT) 사이에는 공백을 한 칸 이상 두세요. (예: 'currency FROM' (O), 'currencyFROM' (X))
2. ```sql ... ``` 형식으로 감싸지 말고 오직 SQL 쿼리 문자열만 반환하세요.
3. 데이터 파괴적인 명령(DROP, DELETE 등)은 절대 금지입니다.
"""
    res = await llm.ainvoke(prompt)
    sql = res.content.replace("```sql", "").replace("```", "").strip()
    
    # [추가] 생성된 쿼리에서 공백이 붙어버리는 케이스를 정규식으로 한 번 더 방어
    sql = re.sub(r'([a-zA-Z0-9_])(FROM|WHERE|ORDER|LIMIT|GROUP|JOIN)', r'\1 \2', sql, flags=re.IGNORECASE)
    
    return {"sql_query": sql}

async def validate_sql_logic(state: LedgerState):
    """SQL 보안 및 정합성 검증."""
    sql = state.get("sql_query", "")
    if not validate_sql_security(sql):
        return {"error": "SECURITY_VIOLATION", "retry_count": state.get("retry_count", 0) + 1}
    
    llm = get_llm()
    prompt = f"다음 SQL이 문법적으로 올바른지 검토하고 PASS 또는 FAIL로 답하세요.\nSQL: {sql}"
    res = await llm.ainvoke(prompt)
    if "PASS" in res.content.upper():
        return {"error": None}
    return {"error": "VALIDATION_FAIL", "retry_count": state.get("retry_count", 0) + 1}

async def graph_generator_node(state: LedgerState):
    """Neo4j Cypher 생성."""
    llm = get_llm()
    prompt = f"Neo4j(Account, Merchant, Transaction)용 Cypher를 작성하세요.\n질문: {state['refined_question']}"
    res = await llm.ainvoke(prompt)
    return {"graph_query": res.content.replace("```cypher", "").replace("```", "").strip()}

async def execute_sql_logic(state: LedgerState):
    """실제 데이터 추출 (에러 시 빈 리스트 반환 보장)"""
    sql_res, graph_res = [], []
    error = None
    
    # [수정] sql_query가 비어있지 않은지 확인
    query = state.get("sql_query", "").strip()
    if query and not state.get("error"):
        try:
            with sql_engine.connect() as conn:
                result = conn.execute(text(query))
                # [수정] 결과가 없을 경우를 대비해 안전하게 변환
                if result.returns_rows:
                    raw_rows = [dict(row._mapping) for row in result]
                    if raw_rows:
                        # Pandas를 거쳐 JSON으로 변환하여 데이터 일관성 확보
                        sql_res = json.loads(pd.Series(raw_rows).to_json(orient='records'))
        except Exception as e:
            logger.error(f"SQL 실행 에러: {e}")
            # [수정] 에러가 나더라도 sql_result는 빈 리스트 []가 되도록 유지 (프론트엔드 방어)
            error = f"SQL_EXEC_ERROR: {str(e)}"

    return {
        "sql_result": sql_res, 
        "graph_result": graph_res, 
        "error": error
    }

async def final_analyzer_node(state: LedgerState):
    """결과 분석 및 시각화 데이터 생성 (배열 길이 일관성 강제)"""
    llm = get_llm()
    data = state.get("sql_result") or state.get("graph_result") or []
    
    # [수정] CHART_JSON 생성 시 모든 배열의 길이를 맞추도록 강력하게 지시
    prompt = f"""아래 데이터를 바탕으로 사용자의 질문에 친절하게 답하고, 시각화가 가능하다면 차트 데이터를 포함하세요.

데이터: {data}
질문: {state['refined_question']}

[차트 생성 규칙]
1. 반드시 [CHART_JSON] 태그 뒤에 JSON 객체를 작성하세요.
2. JSON 구조 예시: {{"data": [{{"label": "항목1", "value": 100}}, {{"label": "항목2", "value": 200}}]}}
3. [중요] 'All arrays must be of the same length' 에러를 방지하기 위해, 리스트 형태보다는 위 예시처럼 객체의 배열 형태를 권장합니다.
4. 만약 데이터가 없거나 시각화가 어려우면 [CHART_JSON] 부분을 아예 생략하세요.
"""
    res = await llm.ainvoke(prompt)
    return {"analysis": res.content}

async def save_history_logic(state: LedgerState):
    """대화 내역 저장."""
    session_id = state.get("session_id", "default")
    history_key = f"chat_history:{session_id}"
    new_msg = f"Q: {state['refined_question']}\nA: {state['analysis'][:100]}..."
    await redis_client.lpush(history_key, new_msg)
    await redis_client.ltrim(history_key, 0, 9) 
    return state