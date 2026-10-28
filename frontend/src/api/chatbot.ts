import { apiClient } from './client';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'model';
  content: string;
}

export interface AIChatRequest {
  student_id?: string | null;
  message: string;
  conversation_history?: ChatMessage[];
}

export interface AIChatResponse {
  reply: string;
  student_name: string;
  student_id: string;
  backlog_count: number;
  risk_level: string;
  suggested_actions: string[];
}

export interface DailyScheduleSlot {
  subject: string;
  hours: number;
  activity: string;
  topics?: string[];
}

export interface BacklogPlan {
  subject: string;
  current_marks?: number;
  status: string;
  problem_identified: string;
  recommended_topics: string[];
  daily_study_time_hrs: number;
  practice_strategy: string;
  revision_strategy: string;
  target_marks: number;
}

export interface StudyPlanResponse {
  student_id: string;
  student_name: string;
  weekly_schedule: Record<string, DailyScheduleSlot[]>;
  backlog_improvement_plans: BacklogPlan[];
  weak_areas: string[];
  generated_at: string;
}

export const chatbotApi = {
  async chatWithCounsellor(req: AIChatRequest): Promise<AIChatResponse> {
    return apiClient<AIChatResponse>('/counselling/chat', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async getStudyPlan(studentId: string): Promise<StudyPlanResponse> {
    return apiClient<StudyPlanResponse>(`/counselling/student/${studentId}/study-plan`);
  },

  async generateStudyPlan(studentId: string): Promise<StudyPlanResponse> {
    return apiClient<StudyPlanResponse>(`/counselling/student/${studentId}/study-plan`, {
      method: 'POST',
    });
  },
};
