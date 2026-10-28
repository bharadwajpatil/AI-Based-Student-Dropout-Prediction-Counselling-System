import { apiClient } from './client';
import type {
  AnalyticsOverview,
  DistributionItem,
  CorrelationData,
} from '../types';

export const analyticsApi = {
  async getOverview(department?: string): Promise<AnalyticsOverview> {
    const qs = department ? `?department=${encodeURIComponent(department)}` : '';
    return apiClient<AnalyticsOverview>(`/analytics/overview${qs}`);
  },

  async getDistribution(department?: string): Promise<{ distribution: DistributionItem[] }> {
    const qs = department ? `?department=${encodeURIComponent(department)}` : '';
    return apiClient<{ distribution: DistributionItem[] }>(`/analytics/distribution${qs}`);
  },

  async getAttendanceVsRisk(department?: string): Promise<CorrelationData> {
    const qs = department ? `?department=${encodeURIComponent(department)}` : '';
    return apiClient<CorrelationData>(`/analytics/attendance-vs-risk${qs}`);
  },

  async getMarksVsRisk(department?: string): Promise<CorrelationData> {
    const qs = department ? `?department=${encodeURIComponent(department)}` : '';
    return apiClient<CorrelationData>(`/analytics/marks-vs-risk${qs}`);
  },

  async getByDepartment(): Promise<{ departments: { department: string; total_students: number; high_risk_count: number }[] }> {
    return apiClient('/analytics/by-department');
  },

  async getBySemester(): Promise<{ semesters: { semester: number; total_students: number; high_risk_count: number }[] }> {
    return apiClient('/analytics/by-semester');
  },

  async getTrend(studentId: string): Promise<{
    student_id: string;
    trend: { semester: number; score: number | null; level: string; attendance: number; marks: number | null }[];
  }> {
    return apiClient(`/analytics/trend?student_id=${studentId}`);
  },

  async downloadHighRiskCsv(department?: string): Promise<Blob> {
    const qs = department ? `?department=${encodeURIComponent(department)}` : '';
    return apiClient<Blob>(`/analytics/export/high-risk${qs}`, {
      headers: { Accept: 'text/csv' },
    });
  },
};
