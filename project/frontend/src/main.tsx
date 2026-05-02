import React from 'react';
import ReactDOM from 'react-dom/client';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './index.css'; // Tailwind 등 전역 스타일을 적용하기 위해 필수 추가

const GOOGLE_CLIENT_ID = "217086331535-n1na3k15bd6c6cllpj1am8hamjsl1ah9.apps.googleusercontent.com";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <QueryClientProvider client={queryClient}>
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <App />
    </GoogleOAuthProvider>
  </QueryClientProvider>
);