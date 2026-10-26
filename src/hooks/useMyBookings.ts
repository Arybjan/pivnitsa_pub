import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../context/useAuth";
import { authStorage } from "../lib/auth-storage";
import { getMyBookings } from "../api/booking";


export function useMyBookings() {
  const { isAuthenticated } = useAuth();


  return useQuery({
    queryKey: ['myBookings'],
    queryFn: async () => {
      const token = await authStorage.getToken();
      if(!token) throw new Error('Не авторизован');

      return getMyBookings(token);
    },
    enabled: isAuthenticated, // запрос только если авторизован
  });
}