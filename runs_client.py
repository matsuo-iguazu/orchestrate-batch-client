import requests
import json
import os
import sys
import csv
import time
from dotenv import load_dotenv

# .env ファイルをロード
load_dotenv()

# --- 設定の読み込み ---
SERVICE_INSTANCE_URL = os.getenv("ORCHESTRATE_BASE_URL")
API_KEY = os.getenv("API_KEY")
AGENT_ID = os.getenv("AGENT_ID")
# Runs APIにはEnvironment IDが必要です
ENVIRONMENT_ID = os.getenv("ENVIRONMENT_ID") 

# --- エンドポイント ---
IAM_TOKEN_ENDPOINT = "https://iam.cloud.ibm.com/identity/token"
RUNS_BASE_URL = f"{SERVICE_INSTANCE_URL}/v1/orchestrate/runs"

# --- 定数 ---
MAX_POLLING_ATTEMPTS = 60  # 最大試行回数 (約5分)
POLLING_INTERVAL = 5       # 待機時間（秒）

# --- 関数 ---

def get_iam_token(api_key: str) -> str:
    """IBM Cloud IAMトークンを取得"""
    url = IAM_TOKEN_ENDPOINT
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": api_key
    }
    
    response = requests.post(url, headers=headers, data=data, timeout=10)
    response.raise_for_status()
    return response.json()["access_token"]

def get_response_from_runs_api(question: str, iam_token: str) -> tuple[str, str]:
    """
    Runs APIを使用して質問を投げ、完了までポーリングし、回答テキストを返す。
    成功時は回答テキスト、失敗時はエラーメッセージを返す。
    """
    
    # 1. Runs APIでエージェントに質問を投げる
    payload = {
        "agent_id": AGENT_ID,
        "environment_id": ENVIRONMENT_ID,
        "message": {
            "role": "user",
            "content": [{"response_type": "text", "text": question}]
        }
    }
    
    try:
        response = requests.post(RUNS_BASE_URL, headers={"Authorization": f"Bearer {iam_token}", "Content-Type": "application/json"}, json=payload, timeout=30)
        response.raise_for_status()
        run_id = response.json()["run_id"]
        
    except Exception as e:
        return f"Runs POST エラー: {type(e).__name__}", "Error"

    # 2. run_idでステータスをポーリング（完了まで待機）
    status_url = f"{RUNS_BASE_URL}/{run_id}"
    
    for attempt in range(MAX_POLLING_ATTEMPTS):
        try:
            status_response = requests.get(status_url, headers={"Authorization": f"Bearer {iam_token}"}, timeout=10)
            status_response.raise_for_status()
            run_status = status_response.json()
            status = run_status.get("status")
            
            # コンソールに進捗を表示
            sys.stdout.write(f" (Status: {status}...)")
            sys.stdout.flush()

            if status == "completed":
                # 成功: 回答テキストを抽出
                agent_response = run_status.get("result", {})
                message_data = agent_response.get("data", {}).get("message", {})
                
                extracted_texts = []
                for content_item in message_data.get("content", []):
                    if content_item.get("response_type") == "text":
                        extracted_texts.append(content_item.get('text', ''))
                
                # 複数テキストがあれば結合、なければ空文字
                final_text = "\n\n".join(extracted_texts).strip()
                
                if final_text:
                    return final_text, "Success"
                else:
                    return "Runs 結果: テキスト抽出失敗", "Error"

            elif status in ["failed", "cancelled", "error"]:
                # 失敗: エラー詳細を返す（簡略化）
                error_detail = run_status.get("error", {}).get("message", "不明なエラー")
                return f"Runs 実行失敗: {error_detail} (Status: {status})", "Error"
            
            # 待機してから再試行
            time.sleep(POLLING_INTERVAL)

        except Exception as e:
            # ポーリング中のネットワークエラーなど
            return f"Runs GET ポーリングエラー: {type(e).__name__}", "Error"
            
    # タイムアウト
    return f"タイムアウト: {MAX_POLLING_ATTEMPTS * POLLING_INTERVAL}秒以内に完了しませんでした", "Error"


def run_batch_query(input_filepath: str):
    """ファイルから質問を読み込み、エージェントと対話し、結果をCSVに書き出す"""
    
    # 必須パラメータのチェック
    if not all([SERVICE_INSTANCE_URL, API_KEY, AGENT_ID, ENVIRONMENT_ID]) or not os.path.exists(input_filepath):
        print("🔴 エラー: 必須設定値（URL, API_KEY, AGENT_ID, ENVIRONMENT_ID）または入力ファイルが不足しています。", file=sys.stderr)
        sys.exit(1)
        
    print("✅ 設定を読み込みました。")

    try:
        # 1. IAMトークンを取得
        iam_token = get_iam_token(API_KEY)
        print("✅ IAMトークンを取得しました。")
        print(f"処理を開始します。対象 Agent ID: {AGENT_ID}")
        
    except Exception:
        sys.exit(1)

    # 2. 質問ファイルを読み込み
    with open(input_filepath, 'r', encoding='utf-8') as f:
        questions = [line.strip() for line in f if line.strip()]

    base_name = os.path.splitext(os.path.basename(input_filepath))[0]
    output_filepath = f"{base_name}_runs_results.csv" # Runs版であることを明記
    
    # ファイル名表示はここで完結
    print(f"処理件数: {len(questions)}件 -> 結果は '{output_filepath}' に書き込まれます。")
    
    # 3. 処理実行とCSVへの書き出し
    with open(output_filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['ID', 'Question', 'Runs_Response', 'Status'])
        writer.writeheader()
        
        for i, q in enumerate(questions):
            n = i + 1
            
            # 処理中の表示（常に一行、\r で行頭に戻る）
            progress_message = f"[{n}/{len(questions)}] 質問: {q[:30]}..."
            print(f"{progress_message:<80}", end='\r')
            sys.stdout.flush()

            response_text, status = get_response_from_runs_api(q, iam_token)
            
            # 処理完了後の最終表示
            if status == "Success":
                # 成功時: プレビューを表示し、行頭に戻る（改行なし）
                preview = response_text.replace('\n', ' ').strip()[:40] + '...' 
                final_message = f"[{n}/{len(questions)}] 質問: {q[:30]}... | 回答: {preview}"
                print(f"{final_message:<150}", end='\r')
            else:
                # 失敗時: エラーメッセージを表示し、この行で改行させる
                final_message = f"[{n}/{len(questions)}] 質問: {q[:30]}... | 🔴 エラー: {response_text}"
                print(f"{final_message}") # エラー時は改行して残す

            writer.writerow({'ID': n, 'Question': q, 'Runs_Response': response_text, 'Status': status})
            
        # ループ終了後、進捗表示をクリア（改行なし）
        print(" " * 150, end='\r') 

    # 完了メッセージのみ表示（ファイル名表示なし、不要な改行なし）
    print(f"🎉 完了しました。")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python orchestrate_runs_client.py <input_file.txt>")
        sys.exit(1)
    
    run_batch_query(sys.argv[1])