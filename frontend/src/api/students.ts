import { apiClient } from './client';
import type { Student, PerformanceRecord, RiskAssessment } from '../types';

export interface StudentListResponse {
  items: Student[];
  next_cursor: string | null;
  has_more: boolean;
  total_count?: number;
}

export interface SubjectPerformanceItem {
  subject_id: string;
  subject_name: string;
  subject_code: string;
  semester: number;
  marks: number;
  grade: string;
  attendance: number;
  is_backlog: boolean;
  status: 'Strong' | 'Average' | 'Weak' | 'Backlog';
  attendance_warning: boolean;
}

export interface SemesterTrendItem {
  semester: number;
  academic_year: string;
  marks: number;
  attendance: number;
  backlogs: number;
}

export interface BacklogDetailItem {
  subject_id: string;
  subject_name: string;
  subject_code: string;
  previous_marks: number;
  status: string;
  priority: 'HIGH' | 'MEDIUM';
  action_advice: string;
}

export interface StudentPerformanceDashboard {
  student_id: string;
  student_name: string;
  erp_id: string;
  department: string;
  semester: number;
  batch: string;
  course?: string | null;

  average_marks: number;
  cgpa: number;
  overall_attendance: number;
  total_subjects: number;
  passed_subjects: number;
  failed_subjects: number;
  active_backlogs: number;
  current_risk_level: string;
  risk_score: number | null;

  subjects: SubjectPerformanceItem[];
  historical_trend: SemesterTrendItem[];
  trend_direction: 'Improving' | 'Stable' | 'Declining';
  attendance_warnings: string[];
  backlogs_list: BacklogDetailItem[];
  risk_factors: Array<{
    name: string;
    risk: number;
    weight: number;
    contribution: number;
    explanation: string;
  }>;
  recommendations: string[];
}

export interface StudentFilterParams {
  cursor?: string;
  limit?: number;
  department?: string;
  semester?: number;
  status?: string;
  level?: string;
  counselling_status?: string;
  search?: string;
  teacher_id?: string;
}

export const studentApi = {
  async listStudents(params: StudentFilterParams = {}): Promise<StudentListResponse> {
    const query = new URLSearchParams();
    if (params.cursor) query.set('cursor', params.cursor);
    if (params.limit) query.set('limit', params.limit.toString());
    if (params.department) query.set('department', params.department);
    if (params.semester) query.set('semester', params.semester.toString());
    if (params.status) query.set('status', params.status);
    if (params.level) query.set('level', params.level);
    if (params.counselling_status) query.set('counselling_status', params.counselling_status);
    if (params.search) query.set('search', params.search);
    if (params.teacher_id) query.set('teacher_id', params.teacher_id);

    const qs = query.toString();
    return apiClient<StudentListResponse>(`/students${qs ? `?${qs}` : ''}`);
  },

  async getStudent(id: string): Promise<Student> {
    return apiClient<Student>(`/students/${id}`);
  },

  async getNextEnrollmentId(params?: {
    department?: string;
    batch?: string;
    admission_year?: string;
  }): Promise<{ enrollment_id: string; erp_id: string }> {
    const query = new URLSearchParams();
    if (params?.department) query.set('department', params.department);
    if (params?.batch) query.set('batch', params.batch);
    if (params?.admission_year) query.set('admission_year', params.admission_year);
    const qs = query.toString();
    return apiClient<{ enrollment_id: string; erp_id: string }>(
      `/students/generate-enrollment-id${qs ? `?${qs}` : ''}`
    );
  },

  async createStudent(data: Partial<Student>): Promise<Student> {
    return apiClient<Student>('/students', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateStudent(id: string, data: Partial<Student>): Promise<Student> {
    return apiClient<Student>(`/students/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async getPerformance(studentId: string): Promise<PerformanceRecord[]> {
    return apiClient<PerformanceRecord[]>(`/students/${studentId}/performance`);
  },

  async upsertPerformance(
    studentId: string,
    semester: number,
    data: {
      attendance: number;
      classes_held: number;
      marks?: number;
      backlogs?: number;
      assignments?: number;
      engagement?: number;
      academic_year?: string;
    },
    version?: number
  ): Promise<PerformanceRecord> {
    return apiClient<PerformanceRecord>(`/students/${studentId}/performance/${semester}`, {
      method: 'PUT',
      ifMatch: version,
      body: JSON.stringify(data),
    });
  },

  async getRisk(studentId: string): Promise<RiskAssessment> {
    return apiClient<RiskAssessment>(`/students/${studentId}/risk`);
  },

  async importStudentsCsv(file: File): Promise<{ job_id: string; message: string }> {
    const formData = new FormData();
    formData.append('file', file);

    return apiClient<{ job_id: string; message: string }>('/students/import', {
      method: 'POST',
      body: formData,
    });
  },

  async getImportJob(jobId: string): Promise<{
    id: string;
    status: string;
    processed_rows: number;
    total_rows: number;
    successful_rows: number;
    failed_rows: number;
    errors: string[];
  }> {
    return apiClient(`/students/import/${jobId}`);
  },

  async exportData(studentId: string): Promise<Record<string, unknown>> {
    return apiClient<Record<string, unknown>>(`/students/${studentId}/export-data`);
  },

  async deleteStudent(studentId: string): Promise<{ status: string; student_id: string }> {
    return apiClient<{ status: string; student_id: string }>(`/students/${studentId}`, {
      method: 'DELETE',
    });
  },

  async listFaculty(department?: string): Promise<FacultyMember[]> {
    const qs = department ? `?department=${encodeURIComponent(department)}` : '';
    return apiClient<FacultyMember[]>(`/students/faculty${qs}`);
  },

  async assignStudentsToFaculty(
    teacherId: string,
    studentIds: string[]
  ): Promise<{ success: boolean; modified_count: number; total_assigned: number }> {
    return apiClient(`/students/faculty/${teacherId}/assign-students`, {
      method: 'POST',
      body: JSON.stringify({ student_ids: studentIds }),
    });
  },

  async unassignStudentFromFaculty(
    teacherId: string,
    studentId: string
  ): Promise<{ success: boolean; modified_count: number; total_assigned: number }> {
    return apiClient(`/students/faculty/${teacherId}/unassign-student/${studentId}`, {
      method: 'DELETE',
    });
  },

  async getMyPerformanceDashboard(): Promise<StudentPerformanceDashboard> {
    return apiClient<StudentPerformanceDashboard>('/students/me/performance-dashboard');
  },

  async getStudentPerformanceDashboard(studentId: string): Promise<StudentPerformanceDashboard> {
    return apiClient<StudentPerformanceDashboard>(`/students/${studentId}/performance-dashboard`);
  },
};

export interface FacultyMember {
  id: string;
  name: string;
  email: string;
  department?: string;
  role: string;
  assigned_student_count?: number;
}



