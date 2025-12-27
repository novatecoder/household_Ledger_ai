from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    애플리케이션 전역 설정 클래스
    Pydantic Settings를 사용하여 환경 변수(.env) 및 기본값을 관리합니다.
    """

    # --- [LLM Configuration] ---
    # 통합 LLM 설정 (Gemini, Grok, vLLM 공유)
    LLM_API_KEY: str = "token-needed"
    LLM_BASE_URL: str = "http://localhost:8000/v1"
    LLM_MODEL_NAME: str = "unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit"
    
    # --- [Database Configuration - PostgreSQL] ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "user"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "ledger_db"
    
    # --- [Cache Configuration - Redis] ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # --- [Knowledge Graph Configuration - Neo4j] ---
    # Bolt 프로토콜을 사용한 그래프 DB 연결 설정
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # --- [Application Settings] ---
    DATA_PATH: str = "data/"
    RUN_MANUAL_TESTS: bool = False

    # Pydantic 설정 구성
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # 정의되지 않은 환경 변수는 무시
    )

# 싱글톤 설정 객체 생성
settings = Settings()