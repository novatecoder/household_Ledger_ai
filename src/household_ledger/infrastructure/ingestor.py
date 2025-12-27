import pandas as pd
import asyncio
import logging
from sqlalchemy import create_engine
from neo4j import GraphDatabase
from tqdm import tqdm
from household_ledger.common.config import settings
from household_ledger.domain.models import Base
from household_ledger.infrastructure.llm_client import UnifiedLlmClient

logger = logging.getLogger(__name__)

class DataIngestor:
    def __init__(self, db_url: str = None):
        # 1. 인프라 연결 설정
        self.db_url = db_url or (
            f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@"
            f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        )
        self.engine = create_engine(self.db_url)
        self.neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        self.llm = UnifiedLlmClient(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model_name=settings.LLM_MODEL_NAME
        )
        
        # 2. 데이터셋 인덱스 정의 (25개 컬럼 구조 기반)
        self.ACC_ID_IDX = 0
        self.TRANS_ID_IDX = 0
        self.TRANS_ACC_ID_IDX = 1
        self.AMOUNT_IDX = 2
        self.CURRENCY_IDX = 3
        self.MERCHANT_IDX = 4
        self.TIMESTAMP_IDX = 24

    def close(self):
        self.neo4j_driver.close()

    def create_tables(self):
        """SQLAlchemy 모델을 기반으로 테이블 생성"""
        Base.metadata.create_all(self.engine)

    def drop_tables(self):
        """데이터 초기화"""
        print("\n🗑️ 모든 SQL 테이블 삭제 중...")
        Base.metadata.drop_all(self.engine)

    async def _classify_category(self, merchant_id: str):
        """LLM을 통한 가맹점 카테고리 분류"""
        if not merchant_id: return "기타"
        prompt = f"가맹점ID '{merchant_id}'를 보고 [식비, 쇼핑, 교통, 주거, 의료, 기타] 중 하나로 분류해줘. 단어만 답해."
        try:
            res = await self.llm.generate_text(prompt)
            return res.strip()
        except Exception:
            return "기타"

    def ingest_sql(self):
        """CSV 데이터를 PostgreSQL에 적재 (FK 제약 조건 해결 버전)"""
        print("\n📥 SQL 데이터 적재 시작...")
        
        try:
            # [1] 데이터 파일 미리 읽기
            df_acc_file = pd.read_csv("data/user_accounts.csv", header=None, on_bad_lines='skip', engine='python')
            df_trans = pd.read_csv("data/transaction_history.csv", header=None, on_bad_lines='skip', engine='python')

            # [2] 모든 계좌 ID 추출 (파일 내 계좌 + 거래 내역 내 계좌 합치기)
            acc_ids_from_file = set(df_acc_file[self.ACC_ID_IDX].astype(str).unique())
            acc_ids_from_trans = set(df_trans[self.TRANS_ACC_ID_IDX].astype(str).unique())
            
            # 두 집합을 합쳐서 실제 DB에 필요한 모든 계좌 목록 생성
            all_unique_accounts = list(acc_ids_from_file.union(acc_ids_from_trans))
            
            # [3] Accounts 적재 (부모 테이블 먼저)
            acc_to_db = pd.DataFrame({
                "account_id": all_unique_accounts,
                "account_type": "CREDITCARD"  # 기본값
            })
            acc_to_db.to_sql("accounts", self.engine, if_exists="append", index=False)
            print(f"✅ Accounts 적재 완료: {len(acc_to_db)} rows (미등록 계좌 포함)")

            # [4] Transactions 적재 (자식 테이블 나중에)
            dt_series = pd.to_datetime(df_trans[self.TIMESTAMP_IDX])
            processed_df = pd.DataFrame({
                "transaction_id": df_trans[self.TRANS_ID_IDX].astype(str),
                "account_id": df_trans[self.TRANS_ACC_ID_IDX].astype(str),
                "transaction_date": dt_series.dt.date,
                "transaction_time": dt_series.dt.time,
                "amount": df_trans[self.AMOUNT_IDX].astype(float),
                "merchant_id": df_trans[self.MERCHANT_IDX].astype(str),
                "currency": df_trans[self.CURRENCY_IDX].astype(str)
            })

            # 중복 제거
            processed_df.drop_duplicates(subset=['transaction_id'], inplace=True)

            # 가맹점 분류 (상위 20개 샘플 대상)
            unique_merchants = processed_df['merchant_id'].unique()[:20]
            merchant_map = {}
            for m in tqdm(unique_merchants, desc="Classifying Merchants"):
                merchant_map[m] = asyncio.run(self._classify_category(m))
            
            processed_df['category'] = processed_df['merchant_id'].map(merchant_map).fillna("기타")
            
            # 최종 적재
            processed_df.to_sql("transactions", self.engine, if_exists="append", index=False)
            print(f"✅ Transactions 적재 완료: {len(processed_df)} rows")

        except Exception as e:
            print(f"❌ SQL 적재 실패: {e}")

    def _ingest_to_neo4j(self):
        """Neo4j 지식 그래프 구축"""
        print("\n🌐 Neo4j 지식 그래프 구축 중...")
        try:
            # 상위 500개 데이터만 그래프화하여 시각화 성능 확보
            df = pd.read_csv("data/transaction_history.csv", header=None, on_bad_lines='skip', engine='python').head(500)
            with self.neo4j_driver.session() as session:
                for _, row in tqdm(df.iterrows(), total=len(df), desc="Graphing"):
                    session.run("""
                        MERGE (a:Account {id: $acc_id})
                        MERGE (m:Merchant {id: $m_id})
                        CREATE (t:Transaction {id: $t_id, amount: $amt, date: $date})
                        CREATE (a)-[:PERFORMED]->(t)-[:AT]->(m)
                    """, acc_id=str(row[self.TRANS_ACC_ID_IDX]), m_id=str(row[self.MERCHANT_IDX]), 
                         t_id=str(row[self.TRANS_ID_IDX]), amt=float(row[self.AMOUNT_IDX]), 
                         date=str(row[self.TIMESTAMP_IDX]))
            print("✅ Neo4j 구축 완료.")
        except Exception as e:
            print(f"❌ Neo4j 실패: {e}")

    def run_all(self):
        """전체 공정 실행"""
        self.create_tables()
        self.ingest_sql()
        self._ingest_to_neo4j()

# --- [CLI 진입점] pyproject.toml에서 호출 ---

def run_cli():
    ingestor = DataIngestor()
    try:
        ingestor.run_all()
    finally:
        ingestor.close()

def run_drop_cli():
    ingestor = DataIngestor()
    try:
        ingestor.drop_tables()
        with ingestor.neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("✅ 모든 데이터가 삭제되었습니다.")
    finally:
        ingestor.close()