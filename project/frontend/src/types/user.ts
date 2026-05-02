export type AppUser = {
  id: string | number; // 기존 number에서 구글 고유 ID(string)도 받을 수 있도록 수정
  username?: string;
  name?: string;       // 구글 로그인에서 받아오는 이름
  email?: string;      // 구글 이메일
  profile_image?: string; // 구글 프로필 이미지 URL
};
