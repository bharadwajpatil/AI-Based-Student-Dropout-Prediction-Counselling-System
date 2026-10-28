import { apiClient } from './client';

export interface SubjectMarks {
  id: string;
  student_id: string;
  subject_id: string;
  subject_name: string;
  subject_code: string;
  semester: number;
  academic_year: string;
  internal_marks?: number | null;
  external_marks?: number | null;
  practical_marks?: number | null;
  assignment_marks?: number | null;
  total_marks: number;
  grade: string;
  attendance: number;
  is_backlog: boolean;
  entered_by?: string | null;
  updated_at: string;
}

export interface MarksEntryPayload {
  internal_marks?: number | null;
  external_marks?: number | null;
  practical_marks?: number | null;
  assignment_marks?: number | null;
  total_marks: number;
  attendance: number;
  semester: number;
  academic_year?: string;
}

export interface StudentBacklogSummary {
  student_id: string;
  student_name: string;
  total_subjects: number;
  passed_subjects: number;
  backlog_count: number;
  backlog_subjects: SubjectMarks[];
}

export interface SubjectStudentItem {
  student_id: string;
  name: string;
  erp_id: string;
  semester: number;
  batch: string;
  marks: SubjectMarks | null;
}

export interface SubjectStudentsResponse {
  subject: {
    id: string;
    name: string;
    code: string;
    department: string;
    semester: number;
  };
  students: SubjectStudentItem[];
}

export interface TeacherAddStudentPayload {
  name: string;
  erp_id?: string;
  email?: string;
  institutional_email?: string;
  phone?: string;
  dob?: string;
  gender?: string;
  address?: string;
  department: string;
  course?: string;
  year?: string;
  semester: number;
  division?: string;
  batch?: string;
  admission_year?: string;
  password?: string;
  authorize_account?: boolean;
  assigned_teacher_ids?: string[];
}

export const marksApi = {
  async enterMarks(
    studentId: string,
    subjectId: string,
    payload: MarksEntryPayload
  ): Promise<SubjectMarks> {
    return apiClient<SubjectMarks>(`/marks/student/${studentId}/subject/${subjectId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async getStudentMarks(studentId: string, semester?: number): Promise<SubjectMarks[]> {
    const qs = semester !== undefined ? `?semester=${semester}` : '';
    return apiClient<SubjectMarks[]>(`/marks/student/${studentId}${qs}`);
  },

  async getStudentBacklogs(studentId: string): Promise<StudentBacklogSummary> {
    return apiClient<StudentBacklogSummary>(`/marks/student/${studentId}/backlogs`);
  },

  async getSubjectStudents(subjectId: string): Promise<SubjectStudentsResponse> {
    return apiClient<SubjectStudentsResponse>(`/marks/subject/${subjectId}/students`);
  },

  async teacherAddStudent(payload: TeacherAddStudentPayload): Promise<any> {
    return apiClient<any>('/teachers/students', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};
