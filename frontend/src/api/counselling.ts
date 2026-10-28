import { apiClient } from './client';
import type { CounsellingCase, CounsellingStatus } from '../types';

export interface CounsellingListResponse {
  items: CounsellingCase[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export const counsellingApi = {
  async getCases(params: {
    status?: CounsellingStatus;
    department?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<CounsellingListResponse> {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.department) query.set('department', params.department);
    if (params.page) query.set('page', params.page.toString());
    if (params.page_size) query.set('page_size', params.page_size.toString());

    const qs = query.toString();
    return apiClient<CounsellingListResponse>(`/counselling${qs ? `?${qs}` : ''}`);
  },

  async getCase(id: string): Promise<CounsellingCase> {
    return apiClient<CounsellingCase>(`/counselling/${id}`);
  },

  async getStudentCase(studentId: string): Promise<CounsellingCase | null> {
    try {
      return await apiClient<CounsellingCase>(`/counselling/student/${studentId}`);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 404) {
        return null;
      }
      throw err;
    }
  },

  async generateRecommendation(
    studentId: string,
    params: { teacher_notes?: string; force_regenerate?: boolean } = {}
  ): Promise<CounsellingCase> {
    return apiClient<CounsellingCase>(`/counselling/student/${studentId}/generate`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async updateCase(
    id: string,
    data: {
      status?: CounsellingStatus;
      assigned_teacher_id?: string;
      escalate_to_hod?: boolean;
      refer_to_counsellor?: boolean;
    }
  ): Promise<CounsellingCase> {
    return apiClient<CounsellingCase>(`/counselling/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async addNote(id: string, content: string): Promise<CounsellingCase> {
    return apiClient<CounsellingCase>(`/counselling/${id}/notes`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },
};
