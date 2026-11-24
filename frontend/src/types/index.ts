export type UserRole = 'SUPERADMIN' | 'ORG_ADMIN' | 'FACULTY' | 'STUDENT';

export interface OrganizationSettings {
  primary_color?: string;
  logo_url?: string;
  allow_student_signup?: boolean;
  allow_student_pdf_download?: boolean;
  enable_video_assistance?: boolean;
  theme_primary_color?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  domain?: string | null;
  is_active: boolean;
  settings: OrganizationSettings;
  created_at: string;
  updated_at: string;
}

export interface UserProfile {
  full_name: string;
  avatar_url?: string | null;
  parent_name?: string | null;
  parent_phone?: string | null;
  metadata?: Record<string, unknown>;
}

export interface User {
  id: string;
  username: string;
  email?: string;
  phone?: string;
  role: UserRole;
  is_active: boolean;
  is_staff: boolean;
  date_joined: string;
  organization?: Organization | null;
  profile?: UserProfile | null;
  permissions?: string[];
}

export interface AuthResponse {
  status: 'SUCCESS' | 'ERROR';
  access: string;
  refresh: string;
  user: User;
  organization?: Organization | null;
  message?: string;
}

export interface TokenRefreshResponse {
  access: string;
  refresh?: string;
}

export interface ExaminationCenter {
  id: string;
  organization: string;
  name: string;
  code: string;
  address?: string | null;
  capacity: number;
  is_active: boolean;
}

export interface Batch {
  id: string;
  organization: string;
  name: string;
  code: string;
  stream: 'JEE_MAIN' | 'JEE_ADVANCED' | 'NEET' | 'OTHER';
  is_active: boolean;
}

export interface StudentBatchEnrollment {
  id: string;
  student: string;
  batch: string;
  center?: string | null;
  roll_number: string;
  enrolled_at: string;
  is_active: boolean;
}
