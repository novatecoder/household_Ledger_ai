import os
import requests

# 1. 데이터 저장 폴더 설정
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"✅ '{DATA_DIR}' 폴더를 생성했습니다.")

# 2. Microsoft Fraud Detection 실제 파일 경로 (대소문자 및 파일명 수정)
BASE_URL = "https://raw.githubusercontent.com/microsoft/DataStoriesSamples/master/samples/FraudDetectionOnADL/Data"

# 말씀하신 리스트에 맞춰 파일명을 매핑합니다.
DATA_SOURCES = {
    "transaction_history.csv": f"{BASE_URL}/transactions.csv",
    "user_accounts.csv": f"{BASE_URL}/accounts.csv"
}

def download_dataset():
    """실제로 존재하는 transactions.csv와 accounts.csv를 다운로드합니다."""
    print("🚀 Microsoft 실데이터 다운로드 시작...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for filename, url in DATA_SOURCES.items():
        file_path = os.path.join(DATA_DIR, filename)
        print(f"📡 {filename} 가져오는 중...")
        try:
            response = requests.get(url, headers=headers, timeout=25)
            
            # 성공 시 저장
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"   ✅ 완료")
            else:
                print(f"   ❌ 실패 ({response.status_code}): 파일명을 다시 확인해주세요.")
        except Exception as e:
            print(f"   ❌ 오류 발생: {e}")

if __name__ == "__main__":
    download_dataset()