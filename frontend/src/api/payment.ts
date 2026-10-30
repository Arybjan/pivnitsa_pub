import { API, apiRequest } from "./client";
import type { PaymentCreate, PaymentResponse } from "../types/api";


export async function createPayment(data: PaymentCreate, token: string): Promise<PaymentResponse> {
  // сказано, что нужен Idempotency-Key, чтобы деньги не списались дважды при двойном клике
  return apiRequest<PaymentResponse>(`${API.payment}/api/v1/payments`, {
    method: 'POST',
    body: JSON.stringify(data),
    token,
    headers: {
      'Idempotency-Key': crypto.randomUUID(), // генерация рандомного ключа
    },
  });
}


export async function getPaymentStatus(paymentId: number, token: string): Promise<PaymentResponse> {
  return apiRequest<PaymentResponse>(`${API.payment}/api/v1/payments/${paymentId}`, { token })
}