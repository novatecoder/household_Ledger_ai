from household_ledger.common.config import Settings

def test_settings_load():
    """기본값 또는 환경 변수가 정상적으로 로드되는지 확인"""
    s = Settings(DB_NAME="test_db")
    assert s.DB_NAME == "test_db"
    assert s.DATA_PATH == "data/"