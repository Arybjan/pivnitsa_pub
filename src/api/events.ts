import { API, apiRequest } from "./client";
import type { EventListResponse } from "../types/api";


export async function getPublishedEvents(limit = 10, offset = 0): Promise<EventListResponse> {
  return apiRequest<EventListResponse>(
    `${API.event}/api/v1/events?limit=${limit}&offset=${offset}`
  );
}