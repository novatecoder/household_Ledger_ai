from typing import Annotated, List, TypedDict, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class LedgerState(TypedDict):
    # 대화 기록
    messages: Annotated[List[BaseMessage], add_messages]
    
    # [추가됨] 질문 정제 및 워크플로우 제어용
    refined_question: str      # 정제된 질문 (KeyError 방지)
    next_step: str             # 다음 노드 결정용
    retry_count: int           # 재시도 횟수 (0 >= 1 에러 방지)
    error: Optional[str]       # 에러 메시지 저장용
    
    # 분석 데이터
    sql_query: str             
    sql_result: List[Dict]     
    graph_query: str           
    graph_result: List[Dict]   
    
    # 최종 결과
    analysis: str              
    chart_data: Dict[str, Any] 
    
    # 세션 정보
    user_id: str
    session_id: str