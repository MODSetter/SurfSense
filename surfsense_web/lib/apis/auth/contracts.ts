/**
 * LOGIN
 */
export type LoginRequest = {
  email: string;
  password: string;
  grant_type?: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
};

/**
 * REGISTER
 */
export type RegisterRequest = {
  email: string;
  password: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
};

export type RegisterResponse = {
  id: number;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  pages_limit: number;
  pages_used: number;
};
