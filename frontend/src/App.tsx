import { useEffect, useState } from "react";

import { api } from "./api";
import { LoginForm } from "./components/LoginForm";
import { RoleWorkspace } from "./components/RoleWorkspaces";
import type { TokenResponse, User } from "./types";

const TOKEN_KEY = "eldercare-token";
const REFRESH_KEY = "eldercare-refresh";
const USER_KEY = "eldercare-user";

export default function App() {
  const [token, setToken] = useState<string>(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [refreshToken, setRefreshToken] = useState<string>(() => localStorage.getItem(REFRESH_KEY) ?? "");
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem(USER_KEY);
    return stored ? (JSON.parse(stored) as User) : null;
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || user) {
      return;
    }
    api.me(token)
      .then((profile) => setUser(profile))
      .catch(() => {
        setToken("");
        setRefreshToken("");
        setUser(null);
      });
  }, [token, user]);

  async function handleLogin(email: string, password: string) {
    setError(null);
    try {
      const response: TokenResponse = await api.login(email, password);
      setToken(response.access_token);
      setRefreshToken(response.refresh_token);
      setUser(response.user);
      localStorage.setItem(TOKEN_KEY, response.access_token);
      localStorage.setItem(REFRESH_KEY, response.refresh_token);
      localStorage.setItem(USER_KEY, JSON.stringify(response.user));
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Login failed");
    }
  }

  async function handleLogout() {
    if (token && refreshToken) {
      await api.logout(refreshToken, token).catch(() => undefined);
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    setToken("");
    setRefreshToken("");
    setUser(null);
  }

  if (!token || !user) {
    return <LoginForm onSubmit={handleLogin} error={error} />;
  }

  return <RoleWorkspace token={token} user={user} onLogout={handleLogout} />;
}
