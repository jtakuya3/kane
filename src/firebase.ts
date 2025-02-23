import { initializeApp } from 'firebase/app';
import { getAuth, browserLocalPersistence, setPersistence, GoogleAuthProvider } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: 'subsidy-chat-platform',
  storageBucket: 'subsidy-chat-platform.appspot.com',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Configure Google Auth Provider
const googleProvider = new GoogleAuthProvider();
googleProvider.addScope('email');
googleProvider.addScope('profile');
googleProvider.setCustomParameters({
  prompt: 'select_account',
  access_type: 'online'
});

// Initialize Firebase with persistence
setPersistence(auth, browserLocalPersistence)
  .then(() => {
    console.log('Firebase persistence set successfully');
  })
  .catch((error) => {
    console.error('Error setting persistence:', error);
  });

// Log initialization
console.log('Firebase initialized with persistence');

export { auth, googleProvider };
