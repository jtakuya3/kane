import { useState } from 'react';
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth';
import { auth } from '../firebase';

const LoginPage = () => {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleGoogleLogin = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const provider = new GoogleAuthProvider();
      const result = await signInWithPopup(auth, provider);
      const user = result.user;
      // セッション設定
      const response = await fetch('/auth/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          uid: user.uid,
          email: user.email,
          gmail: user.email
        }),
        mode: 'cors',
        credentials: 'include'
      });

      if (response.ok) {
        window.location.href = '/select';
      } else {
        throw new Error('認証に失敗しました');
      }
    } catch (error) {
      setError('ログインに失敗しました。もう一度お試しください。');
    } finally {
      setIsLoading(false);
    }
  };

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
          className={`flex items-center justify-center px-4 py-2 ${isLoading ? 'bg-gray-100 cursor-not-allowed' : 'bg-white hover:bg-gray-50'} text-gray-700 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500`}
        >
          {isLoading ? (
            <span className="text-sm font-medium">ログイン中...</span>
          ) : (
            <>
              <img src="https://www.google.com/favicon.ico" alt="Google" className="w-5 h-5 mr-2" />
              <span className="text-sm font-medium">Googleでログイン</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default LoginPage;
