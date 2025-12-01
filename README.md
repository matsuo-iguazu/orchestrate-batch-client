# 🚀 watsonx Orchestrate Batch Client

このツールは、watsonx Orchestrate の Chat Completions API を使用し、テキストファイルに記述された複数の質問（バッチ）をエージェントに送信し、その結果を CSV ファイルにまとめて出力するためのクライアントです。

## 📦 動作環境

* Python 3.x
* Git (リポジトリのクローン用)

## 🛠️ セットアップ手順

### 1. リポジトリのクローン

まず、このリポジトリをローカル環境または Codespaces にクローンします。

```bash
git clone https://github.com/matsuo-iguazu/orchestrate-batch-client
cd orchestrate-batch-client
```

### 2. Python 仮想環境 (venv) の構築

プロジェクトに必要なライブラリをインストールするために、仮想環境を作成し、アクティベートします。

```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境のアクティベート
source venv/bin/activate  # macOS/Linux の場合
# または .venv\Scripts\activate # Windows の場合
```

### 3. 依存ライブラリのインストール

`requirements.txt` に基づいて、必要なライブラリ（`requests` と `python\-dotenv\`）をインストールします。

```bash
pip install -r requirements.txt
```

---

## ⚙️ 認証情報の設定

プロジェクトルートにある隠しファイル **`\.env`** を編集し、認証情報と設定値を記述します。

**`.env`**

```env
# watsonx Orchestrate の設定情報
ORCHESTRATE_BASE_URL="あなたのサービスインスタンスURL"
API_KEY="あなたのAPIキー"
AGENT_ID="あなたのエージェントID"
```

---

## 📝 質問ファイルの準備

実行したい質問を、1行につき1つの質問として記述したテキストファイル（例: `questions.txt`）を準備します。

**`questions.txt`** の例:

```txt
新規のサービス契約を締結する手順を教えてください。
法人として新規の利用契約を結びたい。
契約締結に必要な書類は何ですか？
```

---

## 🏃 実行方法

準備した質問ファイル（例: `questions.txt`）を引数として、スクリプトを実行します。

```bash
python orchestrate_batch_client.py questions.txt
```

### 📤 出力

実行が完了すると、入力ファイル名に基づいたCSVファイルが生成されます。

例: `questions.txt` を実行した場合、`questions_results.csv` が出力されます。

**`questions_results.csv`** の構造:

| ID | Question | Orchestrate_Response | Status |
| :--- | :--- | :--- | :--- |
| 1 | ... | エージェントの回答全文 | Success/Error |
| 2 | ... | エージェントの回答全文 | Success/Error |