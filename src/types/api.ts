export interface User {
  id: number;
  phone: string;
  email: string | null;
  role: 'user' | 'admin' | 'owner';
  is_active: boolean;
  first_name: string | null;
  last_name: string | null;
  avatar_url: string | null;
  created_at: string;
}

export interface UserUpdateRequest {
  first_name?: string;
  last_name?: string;
  email?: string;
  avatar_url: string;
}


export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface AuthResponse extends AuthTokens {
  user: User;
}

export interface OtpSendResponse {
  message: string;
  expires_in: number;
  resend_after: number;
  debug_code?: string; // код приходит только в режиме разработки
}

export interface OtpVerifyResponse {
  verification_token: string;
  expires_in: number;
}


export type EventStatus = 'DRAFT' | 'PUBLISHED' | 'CANCELLED' | 'FINISHED';

export interface Event {
  id: number;
  title: string;
  description: string | null;
  poster_url: string | null;
  starts_at: string;
  ends_at: string | null;
  status: EventStatus;
  created_by: number;
  created_at: string;
  updated_at: string;
}

export interface EventListResponse {
  items: Event[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
}


export type TableStatus = 'ACTIVE' | 'UNAVAILABLE';

export interface Table {
  id: number;
  hall_id: number;
  number: number;
  capacity: number;
  x: number; // центр X
  y: number; // центр Y
  rotation: number;
  width: number; // лучше, чем scaleX, чтобы бэкенд хранил "стол 120px шириной", чем "масштаб 1.0 от базового 120" - заменить в dashboard.js
  height: number;
  description: string;
  status: TableStatus;
  occupied: boolean;
  price: number;
}

export interface MapTable extends Table {
  physically_available: boolean;
  reason: string | null;
}

export interface Hall {
  id: number;
  name: string;
  description: string;
  map_width: number;
  map_height: number;
  is_active: boolean;
}

export interface HallMap {
  hall: Hall;
  starts_at: string | null;
  ends_at: string | null;
  checked_at: string;
  tables: MapTable[];
}


export type BookingStatus = 'PENDING_PAYMENT' | 'CONFIRMED' | 'CANCELLED' | 'EXPIRED';

export interface BookingCreate {
  table_id: number;
  event_id: number;
  guests: number;
  comment?: string;
}

export interface BookingResponse {
  id: number;
  user_id: number;
  table_id: number;
  table_number?: number;
  event_id: number;
  starts_at: string | null;
  booking_date: string | null;
  guests: number;
  phone: string | null;
  guest_name: string | null;
  total_amount: string | null;
  prepayment: string | null;
  prepayment_paid: string | null;
  cancel_reason: string | null;
  comment?: string | null;
  source: string;
  status: BookingStatus;
  expires_at: string;
  created_at: string;
  update_at: string;
}


export type PaymentStatus = 'PENDING' | 'SUCCEEDED' | 'FAILED' | 'REFUND_PENDING' | 'REFUNDED';

export interface PaymentResponse {
  id: number;
  booking_id: number;
  user_id: number;
  amount: string;
  currency: string;
  status: PaymentStatus;
  provider: string;
  provider_payment_id: string | null;
  receipt_url: string | null;
  refund_reason: string | null;
  client_secret: string | null;
  checkout_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaymentCreate {
  booking_id: number;
}


export interface NotificationResponse {
  id: number;
  user_id: number | null;
  title: string;
  message: string;
  type: string;
  related_event_id: number | null;
  related_booking_id: number | null;
  is_read: boolean;
  created_at: string;
}