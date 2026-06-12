import type { AppUser } from './user';

export type AuthResponse = {
  access_token: string;
  token_type?: string;
  user: AppUser;
};
