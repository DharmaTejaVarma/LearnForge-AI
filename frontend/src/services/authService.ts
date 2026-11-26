import { api } from './api';
import { AuthResponse, LoginCredentials, RegisterCredentials, User } from '../types/auth';

export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/auth/login', credentials);
    return response.data;
  },

  async register(credentials: RegisterCredentials): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/auth/register', credentials);
    return response.data;
  },

  async getProfile(): Promise<User> {
    const response = await api.get<User>('/users/me', { timeout: 6000 });
    return response.data;
  },

  async getHealth(): Promise<any> {
    const response = await api.get('/health', { timeout: 6000 });
    return response.data;
  }
};
