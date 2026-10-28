import { apiClient } from './client';

export interface HodStats {
  department: string;
  total_teachers: number;
  total_students: number;
  total_subjects: number;
  high_risk_students: number;
  medium_risk_students: number;
  low_risk_students: number;
  students_with_backlogs: number;
}

export interface TeacherItem {
  id: string;
  name: string;
  email: string;
  phone?: string;
  employee_id?: string;
  department: string;
  designation?: string;
  role: string;
  status: string;
  hod_id?: string;
  assigned_subjects_count: number;
  assigned_students_count: number;
  created_at: string;
}

export interface CreateTeacherPayload {
  name: string;
  email: string;
  phone?: string;
  employee_id?: string;
  department: string;
  designation?: string;
  password: string;
}

export const hodApi = {
  async getStats(): Promise<HodStats> {
    return apiClient<HodStats>('/hod/stats');
  },

  async listTeachers(): Promise<TeacherItem[]> {
    return apiClient<TeacherItem[]>('/hod/teachers');
  },

  async createTeacher(data: CreateTeacherPayload): Promise<TeacherItem> {
    return apiClient<TeacherItem>('/hod/teachers', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateTeacher(id: string, data: Partial<CreateTeacherPayload>): Promise<TeacherItem> {
    return apiClient<TeacherItem>(`/hod/teachers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async deleteTeacher(id: string): Promise<{ success: boolean; message: string }> {
    return apiClient<{ success: boolean; message: string }>(`/hod/teachers/${id}`, {
      method: 'DELETE',
    });
  },
};
