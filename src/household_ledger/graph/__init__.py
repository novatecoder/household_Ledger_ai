from typing import Annotated, TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    """
    LangGraph 에이전트 간에 공유되는 상태 객체입니다.
    """
    # 사용자 및 세션 식별 (5분 캐시 및 권한 관리용)
    user_id: str
    session_id: str
    
    # 데이터 흐름
    question: str
    sql: Optional[str]
    results: Optional[List[Dict[str, Any]]]
    error: Optional[str]
    
    # 방어 로직 및 흐름 제어용
    retry_count: int
    is_cached: bool