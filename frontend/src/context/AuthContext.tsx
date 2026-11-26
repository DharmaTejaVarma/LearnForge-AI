import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, LoginCredentials, RegisterCredentials, AuthContextType } from '../types/auth';
import { authService } from '../services/authService';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function readCachedUser(): User | null {
  try {
    const raw = localStorage.getItem('learnforge_user');
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('learnforge_token'));
  const [user, setUser] = useState<User | null>(() => readCachedUser());
  // Always start in non-loading state — if we have both token AND cached user,
  // the user is immediately authenticated. We validate in the background.
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem('learnforge_token');
      const cached = readCachedUser();
      if (!savedToken) {
        // No token at all — not authenticated, nothing to do
        setUser(null);
        setToken(null);
        return;
      }
      if (cached) {
        // Instantly authenticated from cache; validate token in the background
        setToken(savedToken);
        setUser(cached);
        // Background silent refresh — don't block the UI
        authService.getProfile().then((profile) => {
          localStorage.setItem('learnforge_user', JSON.stringify(profile));
          setUser(profile);
        }).catch((err: any) => {
          const status = err?.response?.status;
          if (status === 401 || status === 403) {
            // Token actually expired/revoked
            localStorage.removeItem('learnforge_token');
            localStorage.removeItem('learnforge_user');
            setUser(null);
            setToken(null);
          }
          // Otherwise (network error, server down) keep the cached session
        });
      } else {
        // Token but no cache — need to fetch profile to authenticate
        setIsLoading(true);
        try {
          const profile = await authService.getProfile();
          localStorage.setItem('learnforge_user', JSON.stringify(profile));
          setUser(profile);
          setToken(savedToken);
        } catch (err: any) {
          const status = err?.response?.status;
          if (status === 401 || status === 403) {
            localStorage.removeItem('learnforge_token');
            localStorage.removeItem('learnforge_user');
            setUser(null);
            setToken(null);
          }
        } finally {
          setIsLoading(false);
        }
      }
    };

    initAuth();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    setIsLoading(true);
    try {
      const data = await authService.login(credentials);
      localStorage.setItem('learnforge_token', data.access_token);
      localStorage.setItem('learnforge_user', JSON.stringify(data.user));
      setToken(data.access_token);
      setUser(data.user);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (credentials: RegisterCredentials) => {
    setIsLoading(true);
    try {
      const data = await authService.register(credentials);
      localStorage.setItem('learnforge_token', data.access_token);
      localStorage.setItem('learnforge_user', JSON.stringify(data.user));
      setToken(data.access_token);
      setUser(data.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('learnforge_token');
    localStorage.removeItem('learnforge_user');
    setUser(null);
    setToken(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
