"""
Neo4j 인프라 클라이언트 유닛 테스트 모듈
지식 그래프 데이터베이스와의 쿼리 실행 및 결과 파싱 로직을 검증합니다.
"""

import pytest
from unittest.mock import MagicMock, patch
from household_ledger.infrastructure.neo4j_client import Neo4jClient


def test_neo4j_execute_query_success(mocker):
    """
    Neo4jClient의 execute_query 메서드가 정상적으로 쿼리를 실행하고
    데이터를 사전(dict) 리스트 형태로 반환하는지 검증합니다.
    """
    # 1. Neo4j 내부 객체 레이어 모킹 (Driver -> Session -> Result -> Record)
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_record = MagicMock()
    
    # [설정] 레코드가 반환할 가짜 데이터 정의
    mock_record.data.return_value = {"n.name": "Apple Inc."}
    # [설정] 결과 객체 순회 시 가짜 레코드를 반환하도록 반복자(iterator) 구성
    mock_result.__iter__.return_value = [mock_record]
    
    # [연결] 각 모킹 객체 간의 호출 관계 정의 (Context Manager 포함)
    mock_session.run.return_value = mock_result
    mock_driver.session.return_value.__enter__.return_value = mock_session
    
    # 2. 클라이언트 테스트 실행 (외부 라이브러리인 GraphDatabase.driver를 패치)
    with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        # 인스턴스 초기화 시 모킹된 드라이버가 주입됨
        client = Neo4jClient()
        
        # 실제 테스트 타겟 메서드 호출
        res = client.execute_query("MATCH (n:Company) RETURN n.name")
        
        # 3. 검증 (Assertions)
        # 결과 리스트의 길이가 정상적인가?
        assert len(res) == 1
        # 반환된 데이터의 값이 기대값과 일치하는가?
        assert res[0]["n.name"] == "Apple Inc."
        # 실제 세션의 run 메서드가 호출되었는가?
        assert mock_session.run.called
        
    print("✅ Neo4jClient 쿼리 실행 및 파싱 테스트 통과")