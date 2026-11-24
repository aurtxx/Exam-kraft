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
  organization?: string;
  name: string;
  code: string;
  address?: string | null;
  capacity: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Batch {
  id: string;
  organization?: string;
  name: string;
  code: string;
  description?: string | null;
  stream: 'JEE_MAIN' | 'JEE_ADVANCED' | 'NEET' | 'OTHER';
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
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

export interface FacultyMember {
  id: string;
  username: string;
  name: string;
  email?: string;
  phone?: string;
  department?: string;
  subjects?: string[];
  centres?: string[];
  batches?: string[];
  is_active: boolean;
  date_joined?: string;
}

export interface StudentMember {
  id: string;
  username: string;
  name: string;
  roll_number: string;
  email?: string;
  phone?: string;
  batch_id?: string;
  centre_id?: string;
  batch_name?: string;
  centre_name?: string;
  is_active: boolean;
  date_joined?: string;
}

export interface BulkImportResult {
  status: 'SUCCESS' | 'ERROR';
  created?: number;
  created_count?: number;
  total_processed?: number;
  updated_count?: number;
  errors?: string[];
  message?: string;
}

export type QuestionTypeValue =
  | 'MCQ_SINGLE'
  | 'MCQ_MULTI'
  | 'NUMERICAL'
  | 'SINGLE_DIGIT'
  | 'TRUE_FALSE'
  | 'ONE_WORD'
  | 'SUBJECTIVE'
  | 'CODING';

export interface QuestionOption {
  id?: string;
  option_key?: string;
  key?: string;
  content_text?: string;
  text?: string;
  is_correct?: boolean;
  order?: number;
}

export interface Question {
  id: string;
  question_bank?: string;
  section?: string;
  section_name?: string;
  question_number: number;
  question_type: QuestionTypeValue | string;
  content_text: string;
  content_html?: string;
  image_url?: string | null;
  explanation?: string;
  difficulty?: 'EASY' | 'MEDIUM' | 'HARD';
  key?: string;
  positive_marks: number;
  negative_marks: number;
  partial_marks: number;
  cmk?: number;
  imk?: number;
  pmk?: number;
  is_cancelled?: boolean;
  canc?: boolean;
  numerical_min?: number | null;
  numerical_max?: number | null;
  coding_language?: string;
  code_boilerplate?: string;
  test_cases?: Array<{ input: string; expected_output: string; is_hidden?: boolean }>;
  options?: QuestionOption[];
  created_at?: string;
  updated_at?: string;
}

export interface QuestionBank {
  id: string;
  name: string;
  exam_type: string;
  description?: string;
  instructions?: string;
  duration_minutes: number;
  is_locked: boolean;
  total_questions?: number;
  subjects?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface ExaminationSection {
  id: string;
  exam: string;
  title: string;
  order: number;
  total_questions: number;
  marks_per_question: number;
  negative_marks: number;
  partial_marks: number;
}

export interface Examination {
  id: string;
  name: string;
  code?: string;
  slug?: string;
  question_paper?: string | null;
  question_paper_id?: string | null;
  instructions?: string;
  duration_minutes: number;
  total_marks?: number;
  passing_marks?: number | null;
  status: 'DRAFT' | 'PUBLISHED' | 'SCHEDULED' | 'CLOSED' | 'EVALUATED';
  start_window?: string | null;
  end_window?: string | null;
  shuffle_questions?: boolean;
  shuffle_options?: boolean;
  camera_proctoring?: boolean;
  max_window_switches?: number;
  allow_section_skip?: boolean;
  practice_mode?: boolean;
  pc_only?: boolean;
  hide_results?: boolean;
  hide_rank?: boolean;
  hide_analytics?: boolean;
  short_url?: string;
  sections?: ExaminationSection[];
  assigned_groups?: string[];
  assigned_centres?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface Notice {
  id: string;
  title: string;
  content: string;
  target_batches?: string[];
  target_centers?: string[];
  target_batch_names?: string[];
  target_center_names?: string[];
  is_active: boolean;
  start_time?: string | null;
  end_time?: string | null;
  created_by_name?: string;
  created_at?: string;
  updated_at?: string;
}
