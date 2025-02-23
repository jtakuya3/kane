import { useState } from 'react';
import { signInWithPopup } from 'firebase/auth';
import { useNavigate } from 'react-router-dom';
import { auth, googleProvider } from '../firebase';
import { useAuth } from '../contexts/AuthContext';
import type { FirebaseError } from 'firebase/app';

export default function LoginPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleGoogleLogin = async () => {
    if (isLoading) return;
    
    try {
      setIsLoading(true);
      setError(null);
      
      await signInWithPopup(auth, googleProvider);
      // Navigation will be handled by AuthContext
      navigate('/select');
    } catch (error) {
      const firebaseError = error as FirebaseError;
      if (firebaseError.code === 'auth/popup-closed-by-user') {
        return; // User closed the popup, no need to show error
      }
      console.error('Login error:', firebaseError);
      const errorMessage = firebaseError.code === 'auth/network-request-failed'
        ? 'ネットワークエラーが発生しました。'
        : 'ログインに失敗しました。';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  if (user) {
    navigate('/select');
    return null;
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        {error && (
          <div className="mb-4 p-4 text-red-700 bg-red-100 rounded-md">
            {error}
          </div>
        )}
        <h1 className="text-2xl font-bold mb-6 text-center">チャットボットログイン</h1>
        <button
          onClick={handleGoogleLogin}
          disabled={isLoading}
          className="flex items-center justify-center w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center">
            {isLoading ? (
              <div className="w-5 h-5 mr-2 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin"></div>
            ) : (
              <img src="https://www.google.com/favicon.ico" alt="Google" className="w-5 h-5 mr-2" />
            )}
            <span>{isLoading ? 'ログイン中...' : 'Googleでログイン'}</span>
          </div>
        </button>
      </div>
    </div>
  );
}
