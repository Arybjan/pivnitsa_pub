import { API, apiRequest } from "./client";
import type { BookingCreate, BookingResponse } from "../types/api";


export async function createBooking(data: BookingCreate, token: string): Promise<BookingResponse> {
  return apiRequest<BookingResponse>(`${API.booking}/api/v1/bookings`, {
    method: 'POST',
    body: JSON.stringify(data),
    token,
  });
}


export async function getMyBookings(token: string): Promise<BookingResponse[]> {
  return apiRequest<BookingResponse[]>(`${API.booking}/api/v1/bookings/my`, { token });
}


export async function cancelBooking(bookingId: number, reason: string, token: string): Promise<BookingResponse> {
  return apiRequest<BookingResponse>(`${API.booking}/api/v1/bookings/${bookingId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
    token,
  });
}