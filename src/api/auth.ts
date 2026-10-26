import { API, apiRequest } from "./client";
import type { AuthResponse, OtpSendResponse, OtpVerifyResponse, User } from "../types/api";


export async function sendOtp(phone: string, purpose: 'register' | 'login' = 'register'): Promise<OtpSendResponse> {
  return apiRequest<OtpSendResponse>(`${API.auth}/api/v1/auth/otp/send`, {
    method: 'POST',
    body: JSON.stringify({ phone, purpose }),
  });
}


export async function verifyOtp(phone: string, code: string, purpose: 'register' | 'login' = 'register'): Promise<OtpVerifyResponse> {
  return apiRequest<OtpVerifyResponse>(`${API.auth}/api/v1/auth/otp/verify`, {
    method: 'POST',
    body: JSON.stringify({ phone, code, purpose }),
  });
}


export async function registerUser(verificationToken: string, password: string, firstName?: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>(`${API.auth}/api/v1/auth/register`, {
    method: 'POST',
    body: JSON.stringify({
      verification_token: verificationToken,
      password,
      first_name: firstName
    }),
  });
}


export async function getMe(token: string): Promise<User> {
  return apiRequest(`${API.auth}/api/v1/users/me`, { token });
}


export async function updateMe(data: { first_name?: string; last_name?: string; email?: string; }, token: string): Promise<User> {
  return apiRequest<User>(`${API.auth}/api/v1/users/me`, {
    method: 'PATCH',
    body: JSON.stringify(data),
    token,
  });
}


export async function loginByToken(verificationToken: string): Promise<AuthResponse> {
  return apiRequest(`${API.auth}/api/v1/auth/login`, {
    method: 'POST',
    body: JSON.stringify({ verification_token: verificationToken }),
  });
}