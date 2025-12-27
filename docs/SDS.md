# [SDS] 지능형 가계부 AI 상세 설계서 (Graph-Enhanced)

## 1. 시스템 아키텍처 (Hybrid DB Architecture)
본 시스템은 정밀한 수치 계산(SQL)과 복잡한 관계 탐색(Graph)을 동시에 지원하기 위해 **PostgreSQL**과 **Neo4j**를 병용합니다.

### 1.1 상태 관리 및 분석 흐름
* **워크플로우**: LangGraph를 통해 에이전트의 추론 상태(`AgentState`)를 관리하며, Redis를 대화 메모리로 사용합니다.
* **데이터 소스**: 이미 확보된 오픈 뱅킹 및 결제 데이터셋을 기반으로 동작합니다.

## 2. 데이터베이스 세부 설계

### 2.1 PostgreSQL (정형 지표 분석)
* **`transaction_history`**: 결제 일시, 금액, 가맹점, 결제 수단 등 원천 내역 저장.
* **`category_master`**: 카테고리 분류 및 예산 설정 정보.

### 2.2 Neo4j 지식 그래프 (관계 분석)
* **노드(Nodes)**: `User`, `Merchant`(가맹점), `Category`, `PaymentMethod`, `Location`
* **관계(Relationships)**:
    * `(:User)-[:PAID_AT]->(:Merchant)`: 사용자가 가맹점에서 결제함.
    * `(:Merchant)-[:BELONGS_TO]->(:Category)`: 가맹점이 특정 카테고리에 속함.
    * `(:Merchant)-[:LOCATED_IN]->(:Location)`: 가맹점의 위치 정보.
* **활용 시나리오**: "주로 야탑동 인근에서 결제하는 가맹점들의 주요 카테고리는?"과 같은 관계형 질문에 대응합니다.

## 3. 멀티 에이전트 오케스트레이션 (LangGraph)

| 노드(Node) | 역할 및 로직 |
| --- | --- |
| **Router** | 질문을 분석하여 `SQL_ONLY`, `NEO4J_RELATION`, `HYBRID`로 작업 분기. |
| **Neo4j Agent** | 관계 탐색이 필요한 경우 Cypher 쿼리를 생성하여 지식 추출. |
| **SQL Agent** | 추출된 문맥(예: 특정 카테고리의 가맹점 리스트)을 받아 PostgreSQL에서 수치 집계. |
| **Answer Validator** | 결과가 사용자의 질문 의도와 일치하는지 최종 검증. |

## 4. 핵심 엔지니어링 전략
* **데이터 연동**: PostgreSQL의 `merchant_id`와 Neo4j의 `Merchant` 노드를 동기화하여 두 DB를 넘나드는 하이브리드 검색을 지원합니다.
* **보안 가드레일**: 개인 식별이 가능한 정보는 마스킹 처리하거나 조회 범위에서 제외하는 `Read-only` 보안 필터를 적용합니다.
* **대화 맥락(History)**: Redis에 저장된 이전 대화 정보를 기반으로 "그중에서 식비는?"과 같은 꼬리 물기 질문에 정확히 답변합니다.