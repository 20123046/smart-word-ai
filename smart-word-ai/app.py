import os
import re
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai

app = FastAPI()

# APIキーを環境変数にセット
API_KEY = "AQ.Ab8RN6Iip980_Ds1bqY_LIHxP_KzU7UwBZOgOAhG3rdFstFIpQ"
os.environ["GEMINI_API_KEY"] = API_KEY

client = None
init_error = ""

try:
    # 引数なしで初期化（環境変数 GEMINI_API_KEY を参照）
    client = genai.Client()
    print("✅ Clientの初期化に成功しました！")
except Exception as e:
    init_error = str(e)
    print(f"⚠️ 初期化エラー: {e}")


class ChatRequest(BaseModel):
    prompt: str
    current_text: str
    style_mode: str = "standard"


class AnalyzeRequest(BaseModel):
    text: str


@app.get("/api/status")
def status_endpoint():
    return {
        "gemini_connected": client is not None,
        "status": "online",
        "init_error": init_error
    }


@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    style_instruction = ""
    if req.style_mode == "ace":
        style_instruction = "【重要】社内で最も評価が高い『エース社員』のスタイル（結論ファースト、簡潔かつ定量的、相手のメリットを強調するトーン）でリライトしてください。"

    if client:
        try:
            sys_prompt = f"""
あなたは企業向け文書作成のプロフェッショナルAIです。
以下の「現在の文章」に対して、ユーザーの「指示」に従って文章を校正・加筆してください。
{style_instruction}

【制約】
・出力は修正・修正後の「本文のみ」を出力してください（挨拶や前置きは不要です）。

現在の文章:
{req.current_text}

ユーザーの指示:
{req.prompt}
"""
            # サポート対象かつ枠があるモデルを指定
            response = client.models.generate_content(
                model="gemini-flash-latest",#gemini-2.0-flash-lite
                contents=sys_prompt,
            )
            updated_text = response.text.strip()
            reply = f"「{req.prompt}」の指示（スタイル: {req.style_mode}）を反映して最適化しました。"
            return {"reply": reply, "updated_text": updated_text, "is_error": False}
        except Exception as e:
            return {
                "reply": f"⚠️ Gemini API呼び出しエラー: {str(e)}",
                "updated_text": req.current_text,
                "is_error": True
            }

    updated_text = req.current_text
    if req.style_mode == "ace":
        updated_text = f"【要約・結論】\n本件の結論として、顧客満足度15%向上を達成しました。\n\n【詳細内容】\n{req.current_text}\n\n【今後のアクション】\n次回打ち合わせにて具体策を提示します。"
        reply = "【エーススタイル適用（ダミー）】結論ファーストかつ定量的な構成に再構築しました。"
    else:
        updated_text = req.current_text + f"\n\n※「{req.prompt}」に基づき文章を調整しました。"
        reply = f"「{req.prompt}」を反映しました（ダミー応答）。"

    return {"reply": reply, "updated_text": updated_text, "is_error": False}


@app.post("/api/analyze")
def analyze_endpoint(req: AnalyzeRequest):
    text = req.text

    risks = []
    if re.search(r'\d{2,4}-\d{2,4}-\d{4}', text):
        risks.append("⚠️ 個人情報検知: 電話番号と思われる記載があります。")
    if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        risks.append("⚠️ 個人情報検知: メールアドレスが含まれています。")
    if any(w in text for w in ["値引き", "値下げ", "無料にする"]):
        risks.append("⚠️ コンプライアンス警告: 価格交渉・値引きに関する表現が含まれています。")

    ai_advice = ""
    if client:
        try:
            prompt = f"以下のビジネス文書の【改善すべき点】や【誤字脱字】を2項目で簡潔に指摘してください:\n{text}"
            res = client.models.generate_content(
                model="gemini-flash-latest",#gemini-2.0-flash-lite #gemini-3.5-flash-lite
                contents=prompt,
            )
            ai_advice = res.text.strip()
        except Exception as e:
            ai_advice = f"（AI分析エラー: {str(e)}）"
    else:
        ai_advice = "文末の表現が統一されており、論理展開も良好です（ダミー分析）。"

    return {
        "risks": risks if risks else ["✅ 法的・コンプライアンス上のリスクは検出されませんでした（安全）。"],
        "advice": ai_advice
    }


app.mount("/", StaticFiles(directory=".", html=True), name="static")