import { useQuery } from "@tanstack/react-query";
import { getNotifications } from "../api/notification";
import { authStorage } from "../lib/auth-storage";
import { useAuth } from "../context/useAuth";


export function useNotifications() {
  const { user } = useAuth();


  return useQuery({
    queryKey: ['notifications', user?.id],
    queryFn: async () => {
      if(!user) throw new Error('Не авторизован');

      const token = await authStorage.getToken();
      if(!token) throw new Error('Нет токена');

      return getNotifications(user.id, token);
    },
    enabled: !!user,
  });
}