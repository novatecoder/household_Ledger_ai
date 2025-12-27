"""
Python 3.12 환경 및 프로젝트 필수 라이브러리 통합 임포트 테스트 (가계부 에이전트 버전)
"""
import sys
import os

def test_setup_verification():
    print("\n" + "="*60)
    print("🚀 Household Ledger AI: Full Dependency Verification")
    print("="*60)
    
    # 검증 대상 (모듈명, 표시 이름)
    # 실제 코드에서 사용되는 핵심 라이브러리들입니다.
    import_targets = [
        ("sqlalchemy", "SQLAlchemy (ORM)"),
        ("psycopg2", "psycopg2 (PostgreSQL)"),
        ("redis", "Redis Client"),
        ("neo4j", "Neo4j Driver"),
        ("fastapi", "FastAPI Framework"),
        ("pydantic", "Pydantic v2"),
        ("pydantic_settings", "Pydantic Settings"),
        ("dotenv", "python-dotenv"),
        ("loguru", "Loguru (Logging)"),
        ("langchain", "LangChain Core"),
        ("langgraph", "LangGraph"),
        ("openai", "OpenAI/vLLM SDK"),
        ("pandas", "Pandas Dataframe"),
        ("numpy", "NumPy"),
        ("streamlit", "Streamlit UI"),
        ("httpx", "HTTPX (Async Client)"),
        ("tqdm", "tqdm (Progress Bar)"),
        ("grandalf", "Grandalf (Graph Layout)"),
        ("requests", "Requests (HTTP Client)")
    ]
    
    passed_count = 0
    failed_modules = []

    for module_name, description in import_targets:
        try:
            # 동적 임포트 실행
            __import__(module_name)
            print(f"✅ [PASS] {description.ljust(30)}")
            passed_count += 1
        except ImportError as e:
            print(f"❌ [FAIL] {description.ljust(30)} -> {e}")
            failed_modules.append({
                "name": module_name,
                "desc": description,
                "error": str(e)
            })

    print("-" * 60)
    
    if not failed_modules:
        print(f"🎉 성공: 총 {passed_count}개의 라이브러리가 정상 로드되었습니다.")
        print(f"런타임 환경: Python {sys.version.split()[0]}")
        print("결과: 가계부 서비스 실행을 위한 최적의 상태입니다.")
    else:
        print(f"⚠️ 경고: 총 {len(failed_modules)}개의 패키지 로드에 실패했습니다.")
        print("\n[실패 리스트]")
        for i, failure in enumerate(failed_modules, 1):
            print(f"{i}. {failure['desc']} ({failure['name']})")
            print(f"   에러 내용: {failure['error']}")
        
        print("\n조치 방법: 'poetry install' 명령어를 실행하여 의존성을 동기화하세요.")
        sys.exit(1)

if __name__ == "__main__":
    test_setup_verification()