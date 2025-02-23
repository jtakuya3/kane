from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from .jwt import create_access_token, verify_token

load_dotenv()

router = APIRouter()

class AuthRequest(BaseModel):
    token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/verify", response_model=TokenResponse)
async def verify_firebase_token(auth_request: AuthRequest):
    try:
        print("Received token:", auth_request.token)
        # For development testing - accept any non-empty token
        if not auth_request.token:
            print("Empty token received")
            raise HTTPException(status_code=401, detail="認証に失敗しました。")
            
        user_data = {
            "uid": "test-user-id",
            "email": "test@example.com"
        }
        access_token = create_access_token(user_data)
        print("Generated access token:", access_token)
        response = {"access_token": access_token, "token_type": "bearer"}
        print("Sending response:", response)
        return response
    except HTTPException as e:
        print("Auth error:", str(e))
        raise e
    except Exception as e:
        print("Auth error:", str(e))
        print("Error details:", e.__dict__)
        raise HTTPException(status_code=401, detail="認証に失敗しました。")
