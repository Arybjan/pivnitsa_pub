import { useCallback, useEffect, useState, type ReactNode } from "react";
import type { User } from "../types/api";
import { authStorage } from "../lib/auth-storage";
import { getMe } from "../api/auth";
import { AuthContext } from "./auth-context";


// обертка, которая хранит user и предоставляет методы login / logout всему дереву
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);


  // есть ли сохраненный токен
  useEffect(() => {
    const init = async () => {
      try {
        const token = await authStorage.getToken();
        if(!token) {
          setIsLoading(false);

          return;
        }

        const me = await getMe(token);
        setUser(me);
      } catch(err) {
        // токен истек или API нет - очищаем, но не падаем
        console.warn('Auth init failed:', err);
        await authStorage.clear();
      } finally {
        setIsLoading(false);
      }
    };

    init();
  }, []);


  const login = useCallback(async (accessToken: string, refreshToken: string, nextUser: User) => {
    await authStorage.setToken(accessToken);
    await authStorage.setRefreshToken(refreshToken);
    setUser(nextUser);
  }, []);


  const logout = useCallback(async () => {
    await authStorage.clear();
    setUser(null);
  }, []);


  const updateUser = useCallback((nextUser: User) => {
    setUser(nextUser);
  }, []);


  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated: !!user, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}