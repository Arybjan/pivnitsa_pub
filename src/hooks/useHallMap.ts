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


export function useHallMap(hallId: number | undefined, startsAt?: string, endsAt?: string) {
  return useQuery({
    queryKey: ['hallMap', hallId, startsAt, endsAt],
    queryFn: () => getHallMap(hallId!, startsAt, endsAt),
    enabled: hallId !== undefined,
  });
}