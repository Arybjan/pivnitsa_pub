import { useQuery } from "@tanstack/react-query";
import { getHalls, getHallMap } from "../api/venue";


export function useHalls() {
  return useQuery({
    queryKey: ['halls'],
    queryFn: getHalls,
    // по умолчанию React Query делает 3 попытки с задержкой. Чтобы не ждать долго:
    retry: 2,
  });
}


export function useHallMap(hallId: number | undefined) {
  return useQuery({
    queryKey: ['hallMap', hallId],
    queryFn: () => getHallMap(hallId!),
    enabled: hallId !== undefined,
  });
}