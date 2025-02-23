from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
from ..auth.jwt import verify_token

load_dotenv()

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    bot_id: str
    conversation_id: str | None = None
    user: str

@router.post("/send", dependencies=[Depends(verify_token)])
async def send_message(chat_request: ChatRequest):
    try:
        # Get bot configuration
        from ..chatbots.routes import CHATBOTS
        bot_config = CHATBOTS.get(chat_request.bot_id)
        if not bot_config:
            raise HTTPException(status_code=404, detail="Chatbot not found")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.dify.ai/v1/chat-messages",
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {bot_config['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "inputs": {},
                    "messages": [{"role": "user", "content": chat_request.message}],
                    "user": chat_request.user,
                    "stream": False,
                    "conversation_id": chat_request.conversation_id
                }
            )
            try:
                response.raise_for_status()
                data = response.json()
                return {
                    "answer": data.get("answer", "申し訳ありません。応答を生成できませんでした。"),
                    "conversation_id": data.get("conversation_id")
                }
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail="チャットボットの応答がタイムアウトしました。")
            except Exception as e:
                print("Dify API error:", str(e))
                print("Response content:", getattr(e, 'response', {}).get('content', 'No response content'))
                print("Response status:", getattr(e, 'response', {}).get('status_code', 'No status code'))
                print("Request URL:", f"{os.getenv('DIFY_BASE_URL')}/completion-messages")
                print("Request payload:", {
                    "inputs": {},
                    "query": chat_request.message,
                    "user": chat_request.user,
                    "response_mode": "blocking",
                    "conversation_id": chat_request.conversation_id
                })
                print("Request headers:", {
                    "Authorization": f"Bearer {bot_config['api_key']}",
                    "Content-Type": "application/json"
                })
                error_msg = str(e)
                if "401" in error_msg:
                    raise HTTPException(status_code=401, detail="チャットボットの認証に失敗しました。")
                elif "404" in error_msg:
                    raise HTTPException(status_code=404, detail="チャットボットが見つかりません。")
                elif "Connection refused" in error_msg:
                    raise HTTPException(status_code=503, detail="Dify APIサービスが利用できません。")
                else:
                    raise HTTPException(status_code=500, detail="チャットメッセージの送信に失敗しました。")
    except HTTPException as e:
        raise e
    except Exception as e:
        error_msg = str(e)
        print("Chat error:", error_msg)
        if "Connection refused" in error_msg:
            error_msg = "Dify API service unavailable"
        elif "401" in error_msg:
            error_msg = "チャットボットの認証に失敗しました。"
        elif "404" in error_msg:
            error_msg = "チャットボットが見つかりません。"
        else:
            error_msg = "チャットメッセージの送信に失敗しました。"
        raise HTTPException(status_code=500, detail=error_msg)
