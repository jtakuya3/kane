export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface Chatbot {
  id: string;
  name: string;
  description: string;
}

export interface ChatResponse {
  message: string;
  conversation_id: string;
}
