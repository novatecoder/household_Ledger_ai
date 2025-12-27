from functools import partial
from langgraph.graph import StateGraph, END
from household_ledger.graph.state import LedgerState
from household_ledger.graph.nodes import (
    query_refiner_node,
    intent_router_node,
    sql_generator_node,
    validate_sql_logic,
    graph_generator_node,
    execute_sql_logic,    # SQL/Graph 통합 실행 노드
    final_analyzer_node,
    save_history_logic
)

def create_household_workflow():
    """
    캐시 기능을 제거하고 SQL/Graph 선택적 조회가 가능한 가계부 워크플로우를 생성합니다.
    """
    workflow = StateGraph(LedgerState)

    # --- [1. 노드 등록 (Node Registration)] ---
    # 이제 캐시 체크 없이 바로 질문 정제부터 시작합니다.
    workflow.add_node("refiner", query_refiner_node)
    workflow.add_node("router", intent_router_node)
    workflow.add_node("sql_gen", sql_generator_node)
    workflow.add_node("validate_sql", validate_sql_logic)
    workflow.add_node("graph_gen", graph_generator_node)
    workflow.add_node("executor", execute_sql_logic)      # SQL 및 Neo4j 통합 실행
    workflow.add_node("analyzer", final_analyzer_node)
    workflow.add_node("save_history", save_history_logic)

    # --- [2. 시작점 설정 (Entry Point)] ---
    # 질문 정제(꼬리물기 해석)가 시스템의 첫 단계입니다.
    workflow.set_entry_point("refiner")

    # --- [3. 엣지 및 조건부 흐름 제어 (Edges & Routing)] ---

    # 1단계: 질문 정제 후 의도 파악(Router)으로 이동
    workflow.add_edge("refiner", "router")

    # 2단계: 의도에 따른 데이터 소스 분기
    # SQL은 정량적 분석, GRAPH는 관계 분석, GENERAL은 일반 답변입니다.
    workflow.add_conditional_edges(
        "router",
        lambda x: x.get("next_step"),
        {
            "SQL": "sql_gen",
            "GRAPH": "graph_gen",
            "GENERAL": "analyzer"
        }
    )

    # 3단계 (SQL 경로): SQL 생성 -> 보안/문법 검증 -> 실행
    workflow.add_edge("sql_gen", "validate_sql")
    workflow.add_conditional_edges(
        "validate_sql",
        lambda x: "exec" if x.get("error") is None or x.get("retry_count", 0) >= 2 else "retry",
        {
            "exec": "executor",
            "retry": "sql_gen"
        }
    )

    # 3단계 (GRAPH 경로): Cypher 생성 -> 실행
    workflow.add_edge("graph_gen", "executor")

    # 4단계: 데이터 실행 후 분석 및 저장
    workflow.add_edge("executor", "analyzer")
    workflow.add_edge("analyzer", "save_history")
    workflow.add_edge("save_history", END)

    return workflow.compile()


# --- [4. 워크플로우 시각화 함수] ---
def display_graph_info(graph):
    """
    업데이트된 워크플로우 구조를 시각화하여 출력합니다.
    """
    print("\n" + "="*60 + "\n📊 Household Ledger AI Workflow (No-Cache Version)\n" + "="*60)
    try:
        graph.get_graph().print_ascii()
    except Exception:
        print(" (ASCII 시각화 생략) ")
    
    print("\n" + "-"*60 + "\n🔗 [Mermaid Code for Visualization]\n")
    print(graph.get_graph().draw_mermaid())
    print("\n" + "-"*60 + "\n")