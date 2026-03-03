import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, setAuthRefreshHandler, type TokenPair, type UserOut } from "../lib/api";

type AuthState = {
  user: UserOut | null;
  accessToken: string | null;
  refreshToken: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const Ctx = createContext<AuthState | undefined>(undefined);

const LS_ACCESS = "newsint.access_token";
const LS_REFRESH = "newsint.refresh_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(localStorage.getItem(LS_ACCESS));
  const [refreshToken, setRefreshToken] = useState<string | null>(localStorage.getItem(LS_REFRESH));
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  const setTokens = (tp: TokenPair | null) => {
    if (!tp) {
      setAccessToken(null);
      setRefreshToken(null);
      localStorage.removeItem(LS_ACCESS);
      localStorage.removeItem(LS_REFRESH);
      return;
    }
    setAccessToken(tp.access_token);
    setRefreshToken(tp.refresh_token);
    localStorage.setItem(LS_ACCESS, tp.access_token);
    localStorage.setItem(LS_REFRESH, tp.refresh_token);
  };

  const loadMe = async (at: string, rt?: string | null) => {
    try {
      const me = await api.auth.me(at);
      setUser(me);
      return;
    } catch {
      // try refresh once
    }
    if (!rt) {
      setTokens(null);
      setUser(null);
      return;
    }
    try {
      const tp = await api.auth.refresh(rt);
      setTokens(tp);
      const me = await api.auth.me(tp.access_token);
      setUser(me);
    } catch {
      setTokens(null);
      setUser(null);
    }
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      if (accessToken) await loadMe(accessToken, refreshToken);
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setAuthRefreshHandler(async () => {
      if (!refreshToken) return null;
      try {
        const tp = await api.auth.refresh(refreshToken);
        setTokens(tp);
        return tp.access_token;
      } catch {
        setTokens(null);
        setUser(null);
        return null;
      }
    });
    return () => setAuthRefreshHandler(null);
  }, [refreshToken]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      accessToken,
      refreshToken,
      loading,
      login: async (email: string, password: string) => {
        const tp = await api.auth.login(email, password);
        setTokens(tp);
        const me = await api.auth.me(tp.access_token);
        setUser(me);
      },
      logout: () => {
        setTokens(null);
        setUser(null);
      },
    }),
    [user, accessToken, refreshToken, loading],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("AuthProvider missing");
  return v;
}

