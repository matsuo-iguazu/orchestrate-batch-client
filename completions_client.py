import requests
import json
import os
import sys
import csv
from dotenv import load_dotenv

# .env ファイルをロード
load_dotenv()

# --- 設定の読み込み ---
SERVICE_INSTANCE_URL = os.getenv("ORCHESTRATE_BASE_URL")
API_KEY = os.getenv("API_KEY")
AGENT_ID = os.getenv("AGENT_ID")

# --- エンドポイント ---
IAM_TOKEN_ENDPOINT = "https://iam.cloud.ibm.com/identity/token"

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

def chat_with_agent(question: str, iam_token: str) -> tuple[str, str]:
    """エージェントに質問を投げ、回答テキストとステータスを返す"""
    url = f"{SERVICE_INSTANCE_URL}/v1/orchestrate/{AGENT_ID}/chat/completions"
    headers = {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [{"role": "user", "content": question}],
        "stream": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result_json = response.json()
        
        # 回答テキストの抽出
        answer_content = result_json['choices'][0]['message']['content']
        
        if isinstance(answer_content, list) and len(answer_content) > 0 and 'text' in answer_content[0]:
            answer_text = answer_content[0]['text']
        elif isinstance(answer_content, str):
            answer_text = answer_content
        else:
            answer_text = "ERROR: 応答形式不正。"
            return answer_text, "Error"
            
        return answer_text, "Success"

    except Exception as e:
        error_message = f"ERROR: {type(e).__name__}"
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
             error_message += f" (Status: {e.response.status_code})"
             
        return error_message, "Error"


def run_batch_query(input_filepath: str):
    """ファイルから質問を読み込み、エージェントと対話し、結果をCSVに書き出す"""
    
    # 必須パラメータのチェック
    if not all([SERVICE_INSTANCE_URL, API_KEY, AGENT_ID]) or not os.path.exists(input_filepath):
        print("🔴 エラー: 必須設定値または入力ファイルが不足しています。", file=sys.stderr)
        sys.exit(1)
        
    print("✅ 設定を読み込みました。")

    try:
        # 1. IAMトークンを取得
        iam_token = get_iam_token(API_KEY)
        print("✅ IAMトークンを取得しました。")
        print(f"評価を開始します。対象 Agent ID: {AGENT_ID}")
        
    except Exception:
        sys.exit(1)

    # 2. 質問ファイルを読み込み
    with open(input_filepath, 'r', encoding='utf-8') as f:
        questions = [line.strip() for line in f if line.strip()]

    base_name = os.path.splitext(os.path.basename(input_filepath))[0]
    output_filepath = f"{base_name}_results.csv"
    
    # ファイル名表示はここで完結
    print(f"処理件数: {len(questions)}件 -> 結果は '{output_filepath}' に書き込まれます。")
    
    # 3. 処理実行とCSVへの書き出し
    with open(output_filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['ID', 'Question', 'Orchestrate_Response', 'Status'])
        writer.writeheader()
        
        for i, q in enumerate(questions):
            n = i + 1
            
            # 処理中の表示（常に一行）
            progress_message = f"[{n}/{len(questions)}] 質問: {q[:30]}... (処理中...)"
            print(f"{progress_message:<80}", end='\r')
            sys.stdout.flush()

            response_text, status = chat_with_agent(q, iam_token)
            
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

            writer.writerow({'ID': n, 'Question': q, 'Orchestrate_Response': response_text, 'Status': status})
            
        # ループ終了後、進捗表示をクリア（改行なし）
        print(" " * 150, end='\r') 

    # 完了メッセージのみ表示（ファイル名表示なし、不要な改行なし）
    print(f"🎉 完了しました。")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python completions_client.py <input_file.txt>")
        sys.exit(1)
    
    run_batch_query(sys.argv[1])