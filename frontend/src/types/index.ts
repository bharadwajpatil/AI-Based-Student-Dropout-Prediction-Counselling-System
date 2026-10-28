export type UserRole = 'admin' | 'hod' | 'teacher' | 'student';

export interface User {
  id: string;
  email: string;
  role: UserRole;
  first_name: string;
  last_name: string;
  department?: string | null;
  phone?: string | null;
  email_verified: boolean;
  phone_verified: boolean;
}

export type RiskLevel = 'Low' | 'Medium' | 'High' | 'Insufficient Data';

export interface RiskFactor {
  name: string;
  risk: number;
  weight: number;
  contribution: number;
  explanation: string;
}

export interface RiskAssessment {
  id?: string;
  student_id: string;
  score: number | null;
  level: RiskLevel;
  confidence: number;
  watchlist: boolean;
  factors: RiskFactor[];
  overrides_applied: string[];
  engine_version: string;
  calculated_at?: string;
}

export type StudentStatus = 'active' | 'graduated' | 'dropped' | 'suspended';

export interface Student {
  id: string;
  erp_id: string;
  name: string;
  email?: string;
  institutional_email?: string;
  department: string;
  semester: number;
  batch: string;
  status: StudentStatus;
  assigned_teacher_ids: string[];
  current_risk?: RiskAssessment | null;
  created_at: string;
  updated_at: string;
}

export interface PerformanceRecord {
  id?: string;
  student_id: string;
  semester: number;
  academic_year: string;
  attendance: number;
  classes_held: number;
  marks?: number | null;
  backlogs?: number | null;
  assignments?: number | null;
  engagement?: number | null;
  version: number;
  created_at?: string;
  updated_at?: string;
}

export type CounsellingStatus = 'pending' | 'in_progress' | 'follow_up' | 'resolved';

export interface TimelineNote {
  note_id: string;
  author_id: string;
  author_name?: string;
  note: string;
  timestamp: string;
}

export interface AiRecommendation {
  summary: string;
  actions: string[];
  follow_up_in_days: number;
  escalate_to_hod: boolean;
  refer_to_counsellor?: boolean;
  ai_source: 'gemini' | 'template';
  generated_at: string;
  is_outdated?: boolean;
}

export interface CounsellingCase {
  id: string;
  student_id: string;
  student_name?: string;
  student_erp?: string;
  department?: string;
  semester?: number;
  risk_level: RiskLevel;
  status: CounsellingStatus;
  assigned_teacher_id?: string;
  ai_recommendation?: AiRecommendation | null;
  notes_timeline: TimelineNote[];
  escalate_to_hod: boolean;
  refer_to_counsellor: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationItem {
  id: string;
  user_id: string;
  title: string;
  message: string;
  type: 'risk_alert' | 'counselling_update' | 'import_status' | 'system';
  read: boolean;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface AnalyticsOverview {
  total_students: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  insufficient_data_count: number;
  pending_counselling_count: number;
  watchlist_count: number;
  average_attendance: number | null;
  average_marks: number | null;
}

export interface DistributionItem {
  level: RiskLevel;
  count: number;
  percentage: number;
}

export interface ScatterPoint {
  student_id: string;
  student_name?: string;
  x: number; // attendance or marks
  y: number; // risk score
  level: RiskLevel;
}

export interface CorrelationData {
  correlation_r: number;
  data_points: ScatterPoint[];
}

export interface ImportProgressEvent {
  job_id: string;
  processed: number;
  total: number;
  successful: number;
  failed: number;
  is_complete: boolean;
  errors?: string[];
}
