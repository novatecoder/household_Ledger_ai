import httpx
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

# 로깅 설정
logger = logging.getLogger(__name__)

class ILlmClient(ABC):
    """
    LLM 클라이언트를 위한 추상 베이스 클래스(Interface)입니다.
    새로운 LLM 서비스 추가 시 이 클래스를 상속받아 구현합니다.
    """
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """텍스트 생성을 위한 추상 메서드"""
        pass

class UnifiedLlmClient(ILlmClient):
    """
    Gemini, Grok, vLLM 등을 하나로 통합한 비동기 LLM 클라이언트입니다.
    OpenAI 호환 규격을 사용하여 다양한 모델을 지원하며, httpx를 통해 비동기로 동작합니다.
    """
    
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        
        # base_url 끝에 /v1이 중복되지 않도록 rstrip 처리
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        
        # 비동기 통신을 위한 타임아웃 설정 (연결 10초, 전체 응답 60초)
        self.timeout = httpx.Timeout(60.0, connect=10.0)

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        httpx.AsyncClient를 사용하여 OpenAI 호환 엔드포인트에 비동기 요청을 보냅니다.
        """
        # API 요청 헤더 구성
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # OpenAI 호환 규격(Chat Completions) 메시지 구성
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # 요청 페이로드 설정 (금융 분석의 정확성을 위해 낮은 temperature 권장)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1  # 결과의 일관성을 위해 0.1로 고정
        }

        # 비동기 HTTP 클라이언트를 통한 호출
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # 비동기 POST 요청 실행
                response = await client.post(
                    f"{self.base_url}/chat/completions", 
                    headers=headers, 
                    json=payload
                )
                
                # HTTP 에러 발생 시 예외 발생
                response.raise_for_status()
                
                # 결과 파싱 및 반환
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP 상태 오류 발생 ({self.model_name}): {e.response.status_code}")
                raise
            except Exception as e:
                logger.error(f"LLM 호출 중 예상치 못한 오류 발생 ({self.model_name}): {e}")
                raise