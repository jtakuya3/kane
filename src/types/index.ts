export interface Chatbot {
  id: string;
  name: string;
  description: string;
}

export interface AuthError extends Error {
  code: string;
}
