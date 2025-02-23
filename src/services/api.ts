import { auth } from '../firebase';

import type { Chatbot } from '../types';

export const chatbots = {
  async list(): Promise<Record<string, Chatbot>> {
    const user = auth.currentUser;
    if (!user) {
      throw new Error('認証が必要です。');
    }

    const response = await fetch('/api/chatbots');
    if (!response.ok) {
      throw new Error('チャットボットの取得に失敗しました。');
    }

    return response.json();
  }
};
