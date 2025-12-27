"""
UnifiedLlmClient 유닛 테스트 모듈
다양한 LLM API(OpenAI 호환)와의 비동기 통신 및 예외 처리 로직을 검증합니다.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from household_ledger.infrastructure.llm_client import UnifiedLlmClient


@pytest.mark.asyncio
async def test_unified_llm_client_generate_success():
    """
    UnifiedLlmClient의 비동기 텍스트 생성 성공 케이스를 검증합니다.
    - API 응답 데이터가 정상적으로 파싱되는지 확인
    - 요청 시 모델명, 시스템 프롬프트, 유저 프롬프트가 정확히 전달되는지 확인
    """
    # 1. 클라이언트 초기화
    client = UnifiedLlmClient(
        api_key="test_api_key", 
        base_url="https://api.example.com", 
        model_name="test-model"
    )
    
    # 2. httpx.AsyncClient.post 메서드 모킹
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # 가짜 응답 객체 설정 (json()은 동기 메서드이므로 MagicMock 사용)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant", 
                        "content": "SELECT * FROM company_master LIMIT 5;"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # 3. 테스트 실행
        prompt = "회사 5개만 보여줘"
        system_prompt = "You are a SQL expert."
        result = await client.generate_text(prompt, system_prompt=system_prompt)
        
        # 4. 결과 검증
        assert "SELECT" in result
        assert "company_master" in result
        
        # 5. API 요청 인자(Payload) 검증
        args, kwargs = mock_post.call_args
        # 모델명이 정확히 주입되었는가?
        assert kwargs["json"]["model"] == "test-model"
        # 시스템 프롬프트가 첫 번째 메시지로 들어갔는가?
        assert kwargs["json"]["messages"][0]["content"] == system_prompt
        # 유저 프롬프트가 두 번째 메시지로 들어갔는가?
        assert kwargs["json"]["messages"][1]["content"] == prompt
        
    print("✅ UnifiedLlmClient 호출 및 인자 검증 테스트 통과")


@pytest.mark.asyncio
async def test_unified_llm_client_http_error():
    """
    API 서버에서 HTTP 에러(4xx, 5xx)를 반환할 때의 예외 처리 로직을 검증합니다.
    """
    client = UnifiedLlmClient(
        api_key="wrong_key", 
        base_url="https://api.example.com", 
        model_name="test-model"
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # HTTP 에러 상황 모킹
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", 
            request=MagicMock(), 
            response=mock_response
        )
        mock_post.return_value = mock_response
        
        # raise_for_status가 호출되면서 예외가 발생하는지 확인
        with pytest.raises(httpx.HTTPStatusError):
            await client.generate_text("test")
            
    print("✅ HTTP 에러(401/403 등) 예외 처리 테스트 통과")


@pytest.mark.asyncio
async def test_unified_llm_client_timeout():
    """
    네트워크 지연으로 인해 타임아웃이 발생할 경우의 동작을 검증합니다.
    """
    client = UnifiedLlmClient(
        api_key="test_key", 
        base_url="https://api.example.com", 
        model_name="test-model"
    )
    
    # AsyncClient.post 호출 시 바로 타임아웃 예외가 발생하도록 설정
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout occurred")):
        with pytest.raises(httpx.TimeoutException):
            await client.generate_text("test")
            
    print("✅ 네트워크 타임아웃 예외 처리 테스트 통과")