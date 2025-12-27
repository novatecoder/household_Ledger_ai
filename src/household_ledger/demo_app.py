import streamlit as st
import httpx
import pandas as pd
import uuid
import json
import re
import os

# --- [SECTION: Configuration - 환경 설정] ---

# 백엔드 API 서버 주소 설정 (Docker 환경 대응)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")

st.set_page_config(page_title="가계부 AI 어드바이저", page_icon="💰", layout="wide")
st.title("💰 AI 가계부 지능형 분석기 (Client)")

# --- [SECTION: Session State - 세션 상태 관리] ---

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if "user_id" not in st.session_state:
    st.session_state.user_id = "demo_user_01"

# --- [SECTION: Sidebar - 사이드바 설정] ---

with st.sidebar:
    st.header("⚙️ 세션 설정")
    st.session_state.user_id = st.text_input("User ID", value=st.session_state.user_id)
    st.session_state.session_id = st.text_input("Session ID", value=st.session_state.session_id)
    
    st.divider()
    if st.button("🔄 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.rerun()

# --- [SECTION: Utility Functions - 유틸리티 함수] ---

def parse_analysis_and_chart(text):
    """분석 텍스트에서 [CHART_JSON] 태그를 찾아 분리합니다."""
    chart_pattern = r"\[CHART_JSON\]\s*(\{.*\})"
    match = re.search(chart_pattern, text, re.DOTALL)
    if match:
        clean_text = text.replace(match.group(0), "").strip()
        try:
            chart_data = json.loads(match.group(1))
            return clean_text, chart_data
        except:
            return clean_text, None
    return text, None

# --- [SECTION: Chat Display - 대화창 표시] ---

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # 저장된 데이터프레임이 있다면 표시
        if "data" in msg and msg["data"] is not None:
            st.dataframe(msg["data"], use_container_width=True)

# --- [SECTION: Chat Input & Logic - 질의응답 처리] ---

if user_query := st.chat_input("질문을 입력하세요 (예: 이번 달 식비 총액 알려줘)"):
    # 1. 사용자 메시지 기록 및 화면 표시
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # 2. 백엔드 API 호출
    with st.chat_message("assistant"):
        with st.spinner("백엔드 에이전트가 분석 중입니다..."):
            try:
                # [핵심] 백엔드 FastAPI의 /api/v1/analyze 엔드포인트 호출
                response = httpx.post(
                    f"{BACKEND_URL}/api/v1/analyze",
                    json={
                        "user_id": st.session_state.user_id,
                        "session_id": st.session_state.session_id,
                        "question": user_query
                    },
                    timeout=60.0 # LLM 추론 시간을 고려하여 넉넉히 설정
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 결과 파싱
                    full_analysis = data.get("analysis", "")
                    clean_text, chart_json = parse_analysis_and_chart(full_analysis)
                    
                    # 3. 분석 과정 (Debug Expander) 표시
                    with st.expander("🔍 에이전트 분석 과정 보기"):
                        st.write(f"**정제된 질문:** {data.get('refined_question')}")
                        st.write(f"**실행 경로:** {data.get('next_step')}")
                        if data.get("sql_query"):
                            st.code(data["sql_query"], language="sql")
                    
                    # 4. 최종 결과 출력
                    st.markdown(clean_text)
                    
                    # 차트 렌더링
                    if chart_json and "data" in chart_json:
                        st.info("📊 데이터 분석 시각화")
                        chart_df = pd.DataFrame(chart_json["data"])
                        st.bar_chart(chart_df.set_index(chart_df.columns[0]))
                    
                    # 5. 세션 상태에 메시지 추가 (결과 테이블 포함)
                    # 백엔드 응답에 sql_result가 포함되어 있다면 데이터프레임으로 변환
                    res_df = pd.DataFrame(data.get("sql_result")) if data.get("sql_result") else None
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": clean_text,
                        "data": res_df
                    })
                    
                else:
                    st.error(f"백엔드 서버 에러: {response.status_code}")
                    
            except Exception as e:
                st.error(f"백엔드 연결 실패: {e}")

    # 화면 갱신을 위해 rerun 호출 (선택 사항)
    # st.rerun()