import React, { useEffect, useState } from 'react';
import { chatbots } from '../services/api';
import type { Chatbot } from '../types';

export default function SelectPage() {
  const [bots, setBots] = useState<Record<string, Chatbot>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadBots = async () => {
      try {
        setLoading(true);
        const response = await chatbots.list();
        setBots(response);
        setError(null);
      } catch (error) {
        setError('チャットボットの読み込みに失敗しました。');
      } finally {
        setLoading(false);
      }
    };
    loadBots();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-red-600">{error}</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">チャットボットを選択</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(bots).map(([id, bot]) => (
          <div key={id} className="border rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
            <h2 className="text-xl font-semibold mb-2">{bot.name}</h2>
            <p className="text-gray-600">{bot.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
