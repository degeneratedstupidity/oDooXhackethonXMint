"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearTokens, getAccessToken, storeTokens } from "./api";

export type Role = "admin" | "hr_officer" | "employee";

export type CurrentUser = {
  id: number;
  login_id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  role: Role;
  avatar: string | null;
  date_of_joining: string;
  must_change_password: boolean;
  company_name: string;
  company_logo: string | null;
  job_position: string;
  department: string;
};

type AuthState = {
  user: CurrentUser | null;
  loading: boolean;
  login: (loginId: string, password: string) => Promise<CurrentUser | null>;
  logout: () => void;
  refreshUser: () => Promise<CurrentUser | null>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refreshUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setLoading(false);
      return null;
    }
    try {
      const current = await apiFetch<CurrentUser>("/me/");
      setUser(current);
      return current;
    } catch {
      clearTokens();
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = useCallback(
    async (loginId: string, password: string) => {
      const tokens = await apiFetch<{ access: string; refresh: string }>(
        "/auth/login/",
        {
          method: "POST",
          body: JSON.stringify({ login_id: loginId, password }),
        },
      );
      storeTokens(tokens);
      return refreshUser();
    },
    [refreshUser],
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
