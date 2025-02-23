from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from typing import Dict, List
from ..auth.jwt import verify_token

load_dotenv()

router = APIRouter()

from pydantic import BaseModel, Field

class Chatbot(BaseModel):
    id: str
    name: str
    description: str
    api_key: str | None = Field(default=None, exclude=True)

CHATBOTS = {
    "daikibo": {
        "id": "JqyaQtp8vMrv70gB",
        "api_key": "app-Di99Cc2UAgjyneStAYjmzRZf",
        "name": "大規模補助金",
        "description": "大規模補助金に関する質問にお答えします"
    },
    "seityoukasoku": {
        "id": "vPRSUhZZcjSjNFFZ",
        "api_key": "app-rzzCkVEVLnVRRgBnqcfaOqJP",
        "name": "成長加速化補助金",
        "description": "成長加速化補助金に関する質問にお答えします"
    },
    "shinjigyo": {
        "id": "ZbNdGSpuv3ia3XPW",
        "api_key": "app-lSG6OVrp6HzveR3edXLBj3us",
        "name": "新事業進出補助金",
        "description": "新事業進出補助金に関する質問にお答えします"
    },
    "osusume": {
        "id": "MlG7dlMiiB2jrEBF",
        "api_key": "app-Sz2ABbpUr2Qr3n51W1oWgPiH",
        "name": "おすすめ補助金まとめ",
        "description": "おすすめ補助金に関する質問にお答えします"
    }
}

@router.get("/list", dependencies=[Depends(verify_token)])
async def list_chatbots() -> Dict[str, Chatbot]:
    return CHATBOTS

@router.get("/{bot_id}")
async def get_chatbot(bot_id: str) -> Chatbot:
    if bot_id not in CHATBOTS:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    return CHATBOTS[bot_id]
