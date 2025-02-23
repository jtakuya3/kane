from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth.routes import router as auth_router
from app.api.chat.routes import router as chat_router
from app.api.chatbots.routes import router as chatbots_router
import os

app = FastAPI()

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
environment = os.getenv("ENVIRONMENT", "development")

# In development, allow all origins
if environment == "development":
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(chatbots_router, prefix="/api/chatbots", tags=["chatbots"])

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
