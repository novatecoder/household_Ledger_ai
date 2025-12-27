"""
HouseholdLedger 인터페이스 무결성 테스트
시스템에서 사용하는 추상 베이스 클래스(ABC)들이 의도대로 작동하는지 검증합니다.
"""

import pytest
from typing import List, Dict, Any
from household_ledger.interfaces.llm import ILlmClient


# --- [Instantiation Tests - 인스턴스화 방지 검증] ---

def test_llm_interface_cannot_instantiate():
    """
    ILlmClient는 추상 클래스이므로 직접 인스턴스화할 때 TypeError가 발생해야 합니다.
    """
    with pytest.raises(TypeError) as excinfo:
        ILlmClient()
    assert "Can't instantiate abstract class ILlmClient" in str(excinfo.value)
