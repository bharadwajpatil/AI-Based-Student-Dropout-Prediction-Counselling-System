import { apiClient } from './client';

export interface SubjectItem {
  id: string;
  name: string;
  code: string;
  department: string;
  year: string;
  semester: number;
  credits: number;
  academic_year: string;
  assigned_teacher_id?: string | null;
  assigned_teacher_name?: string | null;
  hod_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateSubjectPayload {
  name: string;
  code: string;
  department: string;
  year: string;
  semester: number;
  credits: number;
  academic_year?: string;
  assigned_teacher_id?: string | null;
}

export const subjectApi = {
  async listSubjects(params: { department?: string; semester?: number; teacher_id?: string } = {}): Promise<SubjectItem[]> {
    const query = new URLSearchParams();
    if (params.department) query.set('department', params.department);
    if (params.semester) query.set('semester', params.semester.toString());
    if (params.teacher_id) query.set('teacher_id', params.teacher_id);
    const qs = query.toString();
    return apiClient<SubjectItem[]>(`/subjects${qs ? `?${qs}` : ''}`);
  },

  async getSubject(id: string): Promise<SubjectItem> {
    return apiClient<SubjectItem>(`/subjects/${id}`);
  },

  async createSubject(data: CreateSubjectPayload): Promise<SubjectItem> {
    return apiClient<SubjectItem>('/subjects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateSubject(id: string, data: Partial<CreateSubjectPayload>): Promise<SubjectItem> {
    return apiClient<SubjectItem>(`/subjects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async deleteSubject(id: string): Promise<{ success: boolean; message: string }> {
    return apiClient<{ success: boolean; message: string }>(`/subjects/${id}`, {
      method: 'DELETE',
    });
  },

  async assignTeacher(subjectId: string, teacherId: string): Promise<SubjectItem> {
    return apiClient<SubjectItem>(`/subjects/${subjectId}/assign-teacher`, {
      method: 'POST',
      body: JSON.stringify({ teacher_id: teacherId }),
    });
  },

  async bulkAssignSubjects(teacherId: string, subjectIds: string[]): Promise<{
    success: boolean;
    modified_count: number;
    total_assigned_subjects: number;
  }> {
    return apiClient(`/teachers/${teacherId}/assign-subjects`, {
      method: 'POST',
      body: JSON.stringify({ subject_ids: subjectIds }),
    });
  },

  async getMyAssignedSubjects(): Promise<SubjectItem[]> {
    return apiClient<SubjectItem[]>('/teachers/me/subjects');
  },
};
