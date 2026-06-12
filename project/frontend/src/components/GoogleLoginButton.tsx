import { GoogleLogin } from '@react-oauth/google';
import { apiJson } from '../lib/api';
import type { AuthResponse } from '../types/auth';

type GoogleLoginButtonProps = {
  onSuccess: (session: AuthResponse) => void;
  onError: (errorMsg: string) => void;
};

export function GoogleLoginButton({ onSuccess, onError }: GoogleLoginButtonProps) {
  const handleSuccess = async (credentialResponse: any) => {
    try {
      // Send the JWT credential to backend for verification
      const data = await apiJson<AuthResponse>('/api/auth/google', {
        method: 'POST',
        body: JSON.stringify({ access_token: credentialResponse.credential }),
      });

      onSuccess(data);
    } catch (error: any) {
      console.error("Login Error:", error);
      onError(error.message || '로그인 중 오류가 발생했습니다.');
    }
  };

  return (
    <GoogleLogin
      onSuccess={handleSuccess}
      onError={() => onError('구글 로그인 팝업 호출에 실패했습니다.')}
    />
  );
}
