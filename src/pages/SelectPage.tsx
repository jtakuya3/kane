import { useEffect, useState } from 'react';
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
        const botList = await chatbots.list();
        setBots(botList);
      } catch (error) {
        console.error('Error loading chatbots:', error);
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
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="p-4 text-red-700 bg-red-100 rounded-md">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8 text-center">補助金・税務相談チャットボット</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {Object.entries(bots).map(([id, bot]) => (
          <div key={id} className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
            <h2 className="text-xl font-semibold mb-2">{bot.name}</h2>
            <p className="text-gray-600 mb-4">{bot.description}</p>
            <button
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors"
              onClick={() => {/* TODO: Implement chat selection */}}
            >
              選択
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
