import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiClient from '../services/api';
import { User, Organization, OrganizationSettings, AuthResponse } from '../types';

interface AuthContextType {
  user: User | null;
  organization: Organization | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  updateOrganizationBranding: (settings: OrganizationSettings) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(base64));
    if (typeof payload.exp !== 'number') return false;
    return payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

function clearAuthStorage(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('current_user');
  localStorage.removeItem('current_organization');
  localStorage.removeItem('tenant_id');
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const token = localStorage.getItem('access_token');
    if (!token || isTokenExpired(token)) {
      clearAuthStorage();
      return null;
    }
    const cached = localStorage.getItem('current_user');
    return cached ? JSON.parse(cached) : null;
  });
  const [organization, setOrganization] = useState<Organization | null>(() => {
    const token = localStorage.getItem('access_token');
    if (!token || isTokenExpired(token)) {
      return null;
    }
    const cached = localStorage.getItem('current_organization');
    return cached ? JSON.parse(cached) : null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setUser(null);
      setOrganization(null);
      setIsLoading(false);
      return;
    }

    try {
      const response = await apiClient.get('/auth/me/');
      if (response.data?.user) {
        setUser(response.data.user);
        localStorage.setItem('current_user', JSON.stringify(response.data.user));
        if (response.data.user.organization) {
          setOrganization(response.data.user.organization);
          localStorage.setItem('current_organization', JSON.stringify(response.data.user.organization));
          localStorage.setItem('tenant_id', response.data.user.organization.id);
        }
      }
    } catch (err) {
      console.warn('Failed to fetch authenticated user profile:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (username: string, password: string): Promise<AuthResponse> => {
    setIsLoading(true);
    try {
      const response = await apiClient.post<AuthResponse>('/auth/login/', {
        username,
        password,
      });

      const data = response.data;
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      localStorage.setItem('current_user', JSON.stringify(data.user));
      setUser(data.user);

      if (data.organization) {
        setOrganization(data.organization);
        localStorage.setItem('current_organization', JSON.stringify(data.organization));
        localStorage.setItem('tenant_id', data.organization.id);
      } else if (data.user.organization) {
        setOrganization(data.user.organization);
        localStorage.setItem('current_organization', JSON.stringify(data.user.organization));
        localStorage.setItem('tenant_id', data.user.organization.id);
      }

      return data;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        await apiClient.post('/auth/logout/', { refresh: refreshToken }).catch(() => {});
      }
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('current_user');
      localStorage.removeItem('current_organization');
      localStorage.removeItem('tenant_id');
      setUser(null);
      setOrganization(null);
    }
  };

  const updateOrganizationBranding = async (settings: OrganizationSettings) => {
    const response = await apiClient.patch('/organizations/current/', {
      settings,
    });
    if (response.data?.organization) {
      setOrganization(response.data.organization);
      localStorage.setItem('current_organization', JSON.stringify(response.data.organization));
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        organization,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        refreshUser,
        updateOrganizationBranding,
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
