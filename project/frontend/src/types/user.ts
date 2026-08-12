export type AppUser = {
  id: number;
  username?: string;
  name?: string;       // 구글 로그인에서 받아오는 이름
  email?: string;      // 구글 이메일
  profile_image?: string; // 구글 프로필 이미지 URL
};
