import { initializeApp } from 'firebase/app';
import { getAuth, browserLocalPersistence, setPersistence } from 'firebase/auth';

const firebaseConfig = {
  apiKey: "AIzaSyAvdYWWKDkohLRhUaTb0wxbLtUmlF7GS58",
  authDomain: "subsidy-chat-platform.firebaseapp.com",
  projectId: "subsidy-chat-platform",
  storageBucket: "subsidy-chat-platform.appspot.com",
  messagingSenderId: "126236187650",
  appId: "1:126236187650:web:6dbce34d523986f47b5b1b",
  measurementId: "G-1PEZG59REE"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Enable persistent auth state
setPersistence(auth, browserLocalPersistence)
  .catch((error: Error) => {
    console.error('Auth persistence error:', error);
  });

export { auth };
