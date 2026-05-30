import { useGoogleLogin } from '@react-oauth/google';
import type { AppUser } from '../types/user';

type GoogleLoginButtonProps = {
  onSuccess: (user: AppUser) => void;
  onError: (errorMsg: string) => void;
};

export function GoogleLoginButton({ onSuccess, onError }: GoogleLoginButtonProps) {
  const login = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
    try {
      const res = await fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: tokenResponse.access_token }),
      });
      
      if (!res.ok) {
        throw new Error('서버 인증에 실패했습니다.');
      }
      
      const data = await res.json();
      
      // 브라우저 로컬 스토리지에 백엔드 자체 토큰 저장 (이후 API 호출 시 헤더에 포함)
      localStorage.setItem('access_token', data.access_token);
      
      // 부모 컴포넌트(App 등)의 User 상태 업데이트
      onSuccess(data.user);
    } catch (error: any) {
      console.error("Login Error:", error);
      onError(error.message || '로그인 중 오류가 발생했습니다.');
    }
    },
    onError: () => onError('구글 로그인 팝업 호출에 실패했습니다.'),
  });

  return (
    <button
      onClick={() => login()}
      className="text-[10px] sm:text-xs font-bold uppercase tracking-[0.2em] text-foreground hover:opacity-70 transition-opacity py-1"
    >
      Sign in with Google
    </button>
  );
}