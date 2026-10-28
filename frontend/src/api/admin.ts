import { apiClient } from './client';

export interface AdminStats {
  total_hods: number;
  total_teachers: number;
  total_students: number;
  total_subjects: number;
  high_risk_students: number;
  medium_risk_students: number;
  low_risk_students: number;
  students_with_backlogs: number;
  departments: string[];
}

export interface HODItem {
  id: string;
  name: string;
  email: string;
  phone?: string;
  employee_id?: string;
  department: string;
  designation?: string;
  role: string;
  status: string;
  teachers_count: number;
  students_count: number;
  created_at: string;
}

export interface CreateHODPayload {
  name: string;
  email: string;
  phone?: string;
  employee_id?: string;
  department: string;
  designation?: string;
  password: string;
}

export const adminApi = {
  async getStats(): Promise<AdminStats> {
    return apiClient<AdminStats>('/admin/stats');
  },

  async listHods(): Promise<HODItem[]> {
    return apiClient<HODItem[]>('/admin/hods');
  },

  async createHod(data: CreateHODPayload): Promise<HODItem> {
    return apiClient<HODItem>('/admin/hods', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateHod(id: string, data: Partial<CreateHODPayload>): Promise<HODItem> {
    return apiClient<HODItem>(`/admin/hods/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async toggleHodStatus(id: string, status: string): Promise<{ success: boolean; new_status: string }> {
    return apiClient<{ success: boolean; new_status: string }>(`/admin/hods/${id}/status?status_val=${status}`, {
      method: 'PATCH',
    });
  },
};
