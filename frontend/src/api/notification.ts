import { API, apiRequest } from "./client";
import type { NotificationResponse } from "../types/api";


export async function getNotifications(userId: number, token: string): Promise<NotificationResponse[]> {
  return apiRequest<NotificationResponse[]>(`${API.notification}/api/v1/notifications/?user_id=${userId}`, { token });
}


export async function markNotificationAsRead(id: number, token: string): Promise<void> {
  return apiRequest<void>(`${API.notification}/api/v1/notifications/${id}/read`, {
    method: 'PATCH',
    token,
  });
}