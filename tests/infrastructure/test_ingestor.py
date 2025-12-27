import pytest
import pandas as pd
from unittest.mock import MagicMock, AsyncMock, patch
from household_ledger.infrastructure.ingestor import DataIngestor, run_cli

@pytest.fixture
def ingestor(mocker):
    mocker.patch("household_ledger.infrastructure.ingestor.create_engine")
    mocker.patch("household_ledger.infrastructure.ingestor.GraphDatabase.driver")
    return DataIngestor(db_url="postgresql://test:test@localhost/db")

def test_ingest_sql_deduplication(ingestor, mocker):
    """중복된 transaction_id가 있을 때 제거하고 적재하는지 테스트"""
    
    # 1. 중복 데이터 준비 (25개 컬럼 구조)
    mock_row = ["DUP_ID", "ACC_ID", 100.0, "USD", "M1"] + [""] * 19 + ["3/8/2007 18:03"]
    # 동일한 데이터를 두 번 넣음
    mock_trans_df = pd.DataFrame([mock_row, mock_row])
    mock_acc_df = pd.DataFrame([["ACC_ID", "ZIP", "NY", "US", 25, False, 0]])

    # 2. 파일 읽기 모킹
    def side_effect_read(path, **kwargs):
        return mock_acc_df if "accounts" in path else mock_trans_df
    mocker.patch("pandas.read_csv", side_effect=side_effect_read)

    # 3. [핵심] to_sql이 호출될 때 사용된 데이터프레임을 저장할 리스트
    captured_dfs = []
    def side_effect_to_sql(self_df, name, *args, **kwargs):
        captured_dfs.append(self_df)

    # autospec=True를 써야 첫 번째 인자로 self(데이터프레임 인스턴스)가 전달됩니다.
    mocker.patch("pandas.DataFrame.to_sql", autospec=True, side_effect=side_effect_to_sql)
    
    # LLM 분류 모킹
    mocker.patch.object(ingestor, "_classify_category", new_callable=AsyncMock, return_value="기타")

    # 실행
    ingestor.ingest_sql()

    # 4. 검증
    # captured_dfs[0]은 accounts, [1]은 transactions입니다.
    # 중복 데이터 2건이 1건으로 합쳐졌는지 확인
    assert len(captured_dfs[1]) == 1 
    assert captured_dfs[1]["transaction_id"].iloc[0] == "DUP_ID"

@patch("household_ledger.infrastructure.ingestor.DataIngestor")
def test_run_cli_entrypoint(mock_class):
    mock_instance = mock_class.return_value
    run_cli()
    mock_instance.run_all.assert_called_once()