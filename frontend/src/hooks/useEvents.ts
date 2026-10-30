import { useQuery } from "@tanstack/react-query";
import { getPublishedEvents } from "../api/events";


export function usePublishedEvents() {
  return useQuery({
    queryKey: ['events', 'published'],
    queryFn: () => getPublishedEvents(10, 0),
    retry: 2,
  });
}