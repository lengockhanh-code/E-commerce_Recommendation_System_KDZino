"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";

export interface User {
  id: string;
  email: string;
  full_name?: string;
  avatar_url?: string;
  is_active?: boolean;
  is_verified?: boolean;
  provider?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (full_name: string, email: string, password: string) => Promise<void>;
  loginWithGoogle: (googleData: { id_token: string; avatar_url?: string }) => Promise<void>;
  logout: () => void;
  updateUser: (updated: Partial<User>) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    try {
      const storedToken = localStorage.getItem("merrec_token");
      const storedUserStr = localStorage.getItem("merrec_user");

      if (storedToken) {
        setToken(storedToken);
        if (storedUserStr) {
          try {
            setUser(JSON.parse(storedUserStr));
          } catch {
            // invalid JSON fallback
          }
        }

        // Validate token & fetch fresh profile from FastAPI backend
        fetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${storedToken}` }
        })
          .then((res) => {
            if (res.ok) return res.json();
            throw new Error(res.status === 401 ? "Token expired" : "Service unavailable");
          })
          .then((userData) => {
            setUser(userData);
            localStorage.setItem("merrec_user", JSON.stringify(userData));
          })
          .catch((err) => {
            // Keep stored session active unless 401 Unauthorized explicitly returned
            if (err.message === "Token expired") {
              localStorage.removeItem("merrec_token");
              localStorage.removeItem("merrec_user");
              setToken(null);
              setUser(null);
            }
          })
          .finally(() => setIsLoading(false));
      } else {
        setIsLoading(false);
      }
    } catch {
      setIsLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || "Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.");
    }

    const data = await res.json();
    const tokenVal = data.access_token;
    const userVal: User = {
      id: data.user_id,
      email: data.email,
      full_name: data.full_name || email.split("@")[0],
      provider: data.provider || "local"
    };

    setToken(tokenVal);
    setUser(userVal);
    localStorage.setItem("merrec_token", tokenVal);
    localStorage.setItem("merrec_user", JSON.stringify(userVal));
  };

  const register = async (full_name: string, email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name, email, password })
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || "Đăng ký thất bại. Vui lòng thử lại.");
    }

    const data = await res.json();
    const tokenVal = data.access_token;
    const userVal: User = {
      id: data.user_id,
      email: data.email,
      full_name: data.full_name || full_name,
      provider: data.provider || "local"
    };

    setToken(tokenVal);
    setUser(userVal);
    localStorage.setItem("merrec_token", tokenVal);
    localStorage.setItem("merrec_user", JSON.stringify(userVal));
  };

  const loginWithGoogle = async (googleData: { id_token: string; avatar_url?: string }) => {
    const res = await fetch(`${API_BASE}/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(googleData)
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || "Đăng nhập Google thất bại.");
    }

    const data = await res.json();
    const tokenVal = data.access_token;
    const userVal: User = {
      id: data.user_id,
      email: data.email,
      full_name: data.full_name,
      avatar_url: googleData.avatar_url,
      provider: data.provider || "google"
    };

    setToken(tokenVal);
    setUser(userVal);
    localStorage.setItem("merrec_token", tokenVal);
    localStorage.setItem("merrec_user", JSON.stringify(userVal));
  };

  const logout = () => {
    localStorage.removeItem("merrec_token");
    localStorage.removeItem("merrec_user");
    setToken(null);
    setUser(null);
  };

  const updateUser = (updated: Partial<User>) => {
    setUser((prev) => {
      if (!prev) return null;
      const newObj = { ...prev, ...updated };
      localStorage.setItem("merrec_user", JSON.stringify(newObj));
      return newObj;
    });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        register,
        loginWithGoogle,
        logout,
        updateUser
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
