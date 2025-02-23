import axios from "axios";
import type { AuthResponse, Chatbot, ChatResponse } from "@/types";

const api = axios.create({
  baseURL: import.meta.env.PROD 
    ? "https://app-tigsgeal.fly.dev"
    : "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
    "Accept": "application/json"
  }
});

export const setAuthToken = (token: string) => {
  api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
};

export const clearAuthToken = () => {
  delete api.defaults.headers.common["Authorization"];
};

export const auth = {
  verifyToken: async (idToken: string): Promise<AuthResponse> => {
    try {
      console.log("Sending token for verification:", idToken);
      const response = await api.post<AuthResponse>("/api/auth/verify", { token: idToken });
      console.log("Verification response:", response.data);
      if (!response.data.access_token) {
        throw new Error("No access token in response");
      }
      return response.data;
    } catch (error: any) {
      console.error("Token verification error:", error);
      if (error.response) {
        console.error("Error response:", error.response.data);
      }
      throw new Error(error.response?.data?.detail || error.message || "Authentication failed");
    }
  },
};

export const chatbots = {
  list: async (): Promise<Record<string, Chatbot>> => {
    const response = await api.get<Record<string, Chatbot>>("/api/chatbots/list");
    return response.data;
  },
  get: async (id: string): Promise<Chatbot> => {
    const response = await api.get<Chatbot>(`/api/chatbots/${id}`);
    return response.data;
  },
};

export const chat = {
  sendMessage: async (
    message: string,
    botId: string,
    user: string,
    conversationId?: string
  ): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>("/api/chat/send", {
      message,
      bot_id: botId,
      user,
      conversation_id: conversationId,
    });
    return response.data;
  },
};

export default api;
