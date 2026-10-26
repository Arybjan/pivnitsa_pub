import { API, apiRequest } from "./client";
import type { Hall, HallMap } from "../types/api";


export async function getHalls(): Promise<Hall[]> {
  return apiRequest<Hall[]>(`${API.venue}/api/v1/halls`);
} 


export async function getHallMap(hallId: number, startsAt?: string): Promise<HallMap> {
  const url = new URL(`${API.venue}/api/v1/halls/${hallId}/map`);
  if(startsAt) url.searchParams.append('starts_at', startsAt);

  return apiRequest<HallMap>(url.toString());
}