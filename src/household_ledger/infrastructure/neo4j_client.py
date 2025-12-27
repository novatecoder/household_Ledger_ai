from neo4j import GraphDatabase
from household_ledger.common.config import settings

class Neo4jClient:
    def __init__(self):
        # Bolt 프로토콜을 사용하여 Neo4j 연결
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def execute_query(self, query, parameters=None):
        """Cypher 쿼리를 실행하고 결과를 리스트로 반환"""
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]

# 싱글톤 객체 생성
neo4j_client = Neo4jClient()