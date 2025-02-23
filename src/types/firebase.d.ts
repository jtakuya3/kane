/// <reference types="vite/client" />

declare module '@firebase/app' {
  export interface FirebaseApp {}
  export interface FirebaseOptions {
    apiKey: string;
    authDomain: string;
    projectId: string;
    storageBucket: string;
    messagingSenderId: string;
    appId: string;
  }
  export function initializeApp(options: FirebaseOptions): FirebaseApp;
}

declare module '@firebase/auth' {
  import { FirebaseApp } from '@firebase/app';
  
  export interface User {
    uid: string;
    email: string | null;
    displayName: string | null;
    photoURL: string | null;
  }

  export interface Auth {
    app: FirebaseApp;
    currentUser: User | null;
  }

  export interface AuthError extends Error {
    code: string;
    message: string;
  }

  export class GoogleAuthProvider {
    constructor();
    addScope(scope: string): GoogleAuthProvider;
  }

  export interface Persistence {}
  export function getAuth(app?: FirebaseApp): Auth;
  export function setPersistence(auth: Auth, persistence: Persistence): Promise<void>;
  export const browserLocalPersistence: Persistence;
  export function signInWithPopup(auth: Auth, provider: GoogleAuthProvider): Promise<{
    user: User;
  }>;
  export function onAuthStateChanged(
    auth: Auth,
    nextOrObserver: (user: User | null) => void,
    error?: (error: Error) => void
  ): () => void;
}
