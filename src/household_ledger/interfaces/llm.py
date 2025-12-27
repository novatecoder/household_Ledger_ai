from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class ILlmClient(ABC):
    """
    LLM 클라이언트를 위한 추상 베이스 클래스(Interface)입니다.
    다양한 LLM 엔진(vLLM, Gemini 등)을 일관된 방식으로 호출하기 위한 규격을 정의합니다.
    """
    
    @abstractmethod
    async def generate_sql(self, prompt: str, schema_info: str) -> str:
        """
        사용자의 자연어 질문과 데이터베이스 스키마 정보를 입력받아 실행 가능한 SQL을 생성합니다.
        
        Args:
            prompt (str): 사용자의 질문 텍스트
            schema_info (str): 테이블 및 컬럼 정보 (동적 스키마)
            
        Returns:
            str: 생성된 SQL 쿼리 문자열
        """
        pass

    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        일반적인 텍스트 생성 및 대화를 수행합니다.
        
        Args:
            prompt (str): 사용자 프롬프트
            system_prompt (Optional[str]): 시스템 역할 정의 프롬프트
            
        Returns:
            str: 생성된 응답 텍스트
        """
        pass

    @abstractmethod
    async def invoke(self, prompt: str) -> str:
        """
        단순 텍스트 호출 인터페이스입니다.
        
        Args:
            prompt (str): 입력 프롬프트
            
        Returns:
            str: 응답 결과
        """
        pass