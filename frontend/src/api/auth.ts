import { apiClient, setTokens, clearTokens } from './client';
import type { User } from '../types';

export interface LoginParams {
  email: string;
  password: string;
}

export interface RegisterParams {
  name: string;
  email: string;
  password: string;
  role: string;
  erp_id?: string;
  department?: string;
  phone?: string;
  phone_e164?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export const authApi = {
  async login(params: LoginParams): Promise<AuthResponse> {
    const res = await apiClient<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(params),
    });
    setTokens(res.access_token);
    return res;
  },

  async register(params: RegisterParams): Promise<{ message: string; details?: unknown }> {
    return apiClient<{ message: string; details?: unknown }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async verifyEmail(params: { token?: string; code?: string; email?: string }): Promise<{ message: string }> {
    return apiClient<{ message: string }>('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async forgotPassword(params: { identifier: string; channel?: 'email' | 'sms' }): Promise<{ message: string }> {
    return apiClient<{ message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async resetPassword(params: {
    token?: string;
    identifier?: string;
    otp?: string;
    new_password: string;
  }): Promise<{ message: string }> {
    return apiClient<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async getMe(): Promise<User> {
    return apiClient<User>('/auth/me');
  },

  async logout(): Promise<void> {
    try {
      await apiClient('/auth/logout', { method: 'POST' });
    } finally {
      clearTokens();
    }
  },
};
