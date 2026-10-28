import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { subjectApi, type SubjectItem } from '../../api/subjects';
import {
  marksApi,
  type SubjectStudentsResponse,
  type MarksEntryPayload,
  type TeacherAddStudentPayload,
} from '../../api/marks';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { studentApi } from '../../api/students';
import {
  BookOpen,
  ClipboardList,
  Save,
  UserPlus,
  RefreshCw,
  AlertTriangle,
  X,
  Lock,
  Search,
  Sparkles,
  Eye,
  EyeOff,
  ShieldCheck,
  Key,
} from 'lucide-react';

export const MarksEntryPage: React.FC = () => {
  const { user } = useAuth();
  const { success, error } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [assignedSubjects, setAssignedSubjects] = useState<SubjectItem[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>(
    searchParams.get('subject_id') || ''
  );
  const [data, setData] = useState<SubjectStudentsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [savingRowId, setSavingRowId] = useState<string | null>(null);
  const [search, setSearch] = useState<string>('');

  // Editable row states: map studentId -> draft MarksEntryPayload
  const [drafts, setDrafts] = useState<Record<string, MarksEntryPayload>>({});

  // Add Student Modal State (Section 9)
  const [isAddStudentModalOpen, setIsAddStudentModalOpen] = useState<boolean>(false);
  const [addingStudent, setAddingStudent] = useState<boolean>(false);
  const [showStudentPassword, setShowStudentPassword] = useState<boolean>(false);
  const [studentForm, setStudentForm] = useState<
    TeacherAddStudentPayload & { confirm_password?: string; authorize_account?: boolean }
  >({
    name: '',
    erp_id: '',
    email: '',
    phone: '',
    dob: '',
    gender: 'Male',
    address: '',
    department: user?.department || 'Computer Science',
    course: 'B.Tech',
    year: '3rd Year',
    semester: 5,
    division: 'A',
    batch: '2022-26',
    admission_year: '2022',
    password: '',
    confirm_password: '',
    authorize_account: true,
  });

  // Load Teacher's Subjects
  useEffect(() => {
    async function loadSubjects() {
      try {
        const subs = await subjectApi.getMyAssignedSubjects();
        setAssignedSubjects(subs);
        if (!selectedSubjectId && subs.length > 0) {
          setSelectedSubjectId(subs[0].id);
        }
      } catch (err: any) {
        console.error('Failed to load teacher subjects', err);
      }
    }
    loadSubjects();
  }, []);

  // Fetch Subject Roster & Marks
  const fetchStudents = useCallback(async () => {
    if (!selectedSubjectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await marksApi.getSubjectStudents(selectedSubjectId);
      setData(res);

      // Initialize drafts
      const initialDrafts: Record<string, MarksEntryPayload> = {};
      res.students.forEach((s) => {
        const m = s.marks;
        initialDrafts[s.student_id] = {
          internal_marks: m?.internal_marks ?? null,
          external_marks: m?.external_marks ?? null,
          practical_marks: m?.practical_marks ?? null,
          assignment_marks: m?.assignment_marks ?? null,
          total_marks: m ? m.total_marks : 0,
          attendance: m ? m.attendance : 100,
          semester: res.subject.semester,
          academic_year: m?.academic_year || '2024-25',
        };
      });
      setDrafts(initialDrafts);
    } catch (err: any) {
      console.error(err);
      error('Failed to Load Roster', err.message || 'Could not fetch class marks.');
    } finally {
      setLoading(false);
    }
  }, [selectedSubjectId, error]);

  useEffect(() => {
    fetchStudents();
    if (selectedSubjectId) {
      setSearchParams({ subject_id: selectedSubjectId });
    }
  }, [fetchStudents, selectedSubjectId, setSearchParams]);

  const handleFieldChange = (
    studentId: string,
    field: keyof MarksEntryPayload,
    value: any
  ) => {
    setDrafts((prev) => {
      const current = prev[studentId] || {
        total_marks: 0,
        attendance: 100,
        semester: data?.subject.semester || 1,
      };

      const updated = { ...current, [field]: value };

      // Auto-compute total marks if component marks are modified
      if (
        field === 'internal_marks' ||
        field === 'external_marks' ||
        field === 'practical_marks' ||
        field === 'assignment_marks'
      ) {
        const internal = Number(updated.internal_marks) || 0;
        const external = Number(updated.external_marks) || 0;
        const practical = Number(updated.practical_marks) || 0;
        const assignment = Number(updated.assignment_marks) || 0;
        const sum = internal + external + practical + assignment;
        if (sum > 0) {
          updated.total_marks = Math.min(100, sum);
        }
      }

      return { ...prev, [studentId]: updated };
    });
  };

  const calculateGradePreview = (total: number) => {
    if (total >= 90) return 'O';
    if (total >= 80) return 'A+';
    if (total >= 70) return 'A';
    if (total >= 60) return 'B+';
    if (total >= 50) return 'B';
    if (total >= 40) return 'C';
    return 'F';
  };

  const handleSaveMarks = async (studentId: string) => {
    if (!selectedSubjectId) return;
    const draft = drafts[studentId];
    if (!draft) return;

    setSavingRowId(studentId);
    try {
      const updatedMarks = await marksApi.enterMarks(studentId, selectedSubjectId, draft);
      success(
        'Marks Recorded',
        `Marks & Attendance updated. Risk engine recalculated semester performance.`
      );

      // Update in data
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          students: prev.students.map((st) =>
            st.student_id === studentId ? { ...st, marks: updatedMarks } : st
          ),
        };
      });
    } catch (err: any) {
      error('Failed to Save', err.message || 'Could not record marks.');
    } finally {
      setSavingRowId(null);
    }
  };

  const fetchTeacherNextErp = useCallback(async (dept: string, bch?: string, admYear?: string) => {
    try {
      const res = await studentApi.getNextEnrollmentId({
        department: dept,
        batch: bch,
        admission_year: admYear,
      });
      if (res?.enrollment_id) {
        setStudentForm((prev) => ({
          ...prev,
          erp_id: prev.erp_id ? prev.erp_id : res.enrollment_id,
        }));
      }
    } catch {
      // Graceful fallback
    }
  }, []);

  const openEnrollStudentModal = () => {
    setIsAddStudentModalOpen(true);
    fetchTeacherNextErp(
      studentForm.department || user?.department || 'Computer Science',
      studentForm.batch,
      studentForm.admission_year
    );
  };

  const handleAddStudentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (studentForm.password && studentForm.password !== studentForm.confirm_password) {
      error('Password Error', 'Passwords do not match.');
      return;
    }

    if (studentForm.password && !studentForm.email?.trim()) {
      error('Email Required', 'Student Email is required to authorize login access.');
      return;
    }

    setAddingStudent(true);
    try {
      const finalErp = studentForm.erp_id?.trim() ? studentForm.erp_id.trim().toUpperCase() : undefined;
      const payload: TeacherAddStudentPayload = {
        name: studentForm.name,
        erp_id: finalErp,
        email: studentForm.email || undefined,
        institutional_email: studentForm.email || undefined,
        phone: studentForm.phone || undefined,
        dob: studentForm.dob || undefined,
        gender: studentForm.gender || undefined,
        address: studentForm.address || undefined,
        department: studentForm.department,
        course: studentForm.course,
        year: studentForm.year,
        semester: Number(studentForm.semester),
        division: studentForm.division,
        batch: studentForm.batch,
        admission_year: studentForm.admission_year,
        password: studentForm.password || undefined,
        authorize_account: studentForm.authorize_account !== false,
      };

      await marksApi.teacherAddStudent(payload);
      const authNotice = studentForm.password ? ' Login credentials created and authorized.' : '';
      success(
        'Student Enrolled',
        `${studentForm.name} added under your mentorship and enrolled in class.${authNotice}`
      );
      setIsAddStudentModalOpen(false);
      setStudentForm({
        name: '',
        erp_id: '',
        email: '',
        phone: '',
        dob: '',
        gender: 'Male',
        address: '',
        department: user?.department || 'Computer Science',
        course: 'B.Tech',
        year: '3rd Year',
        semester: 5,
        division: 'A',
        batch: '2022-26',
        admission_year: '2022',
        password: '',
        confirm_password: '',
        authorize_account: true,
      });
      fetchStudents();
    } catch (err: any) {
      error('Enrollment Failed', err.message || 'Could not register student.');
    } finally {
      setAddingStudent(false);
    }
  };

  const filteredStudents =
    data?.students.filter(
      (s) =>
        s.name.toLowerCase().includes(search.toLowerCase()) ||
        s.erp_id.toLowerCase().includes(search.toLowerCase())
    ) || [];

  // Summary Metrics
  const totalStudents = data?.students.length || 0;
  const gradedStudents = data?.students.filter((s) => s.marks !== null).length || 0;
  const backlogsCount =
    data?.students.filter((s) => s.marks && s.marks.is_backlog).length || 0;
  const avgAttendance =
    gradedStudents > 0
      ? Math.round(
          (data?.students.reduce((acc, s) => acc + (s.marks?.attendance || 0), 0) || 0) /
            gradedStudents
        )
      : null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-up">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-sand-200 dark:border-charcoal-800">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink-900 dark:text-sand-100 flex items-center">
            <ClipboardList className="w-8 h-8 mr-3 text-clay-500" />
            Subject Gradebook & Continuous Evaluation
          </h1>
          <p className="text-xs sm:text-sm text-ink-500 dark:text-sand-400 mt-1">
            Section 11 &amp; 12: Record internal/external marks and attendance per subject. Failing grades automatically trigger backlog detection and risk recalibration.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchStudents}
            disabled={loading}
            className="inline-flex items-center px-3.5 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs font-semibold text-ink-700 dark:text-sand-300 hover:bg-sand-50 dark:hover:bg-charcoal-750 transition-all shadow-soft"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={openEnrollStudentModal}
            className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
          >
            <UserPlus className="w-4 h-4 mr-1.5" />
            Enroll Student (Section 9)
          </button>
        </div>
      </div>

      {/* Subject Selection & Summary Bar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Subject Picker */}
        <div className="lg:col-span-1 bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft">
          <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1.5 flex items-center">
            <BookOpen className="w-3.5 h-3.5 mr-1.5 text-clay-500" />
            Select Assigned Subject
          </label>
          <select
            value={selectedSubjectId}
            onChange={(e) => setSelectedSubjectId(e.target.value)}
            className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
          >
            {assignedSubjects.length === 0 ? (
              <option value="">No subjects assigned</option>
            ) : (
              assignedSubjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} - {s.name} (Sem {s.semester})
                </option>
              ))
            )}
          </select>

          {data && (
            <div className="mt-3 pt-3 border-t border-sand-200 dark:border-charcoal-700 text-[11px] text-ink-500 dark:text-sand-400 space-y-1">
              <p>
                <strong>Dept:</strong> {data.subject.department}
              </p>
              <p>
                <strong>Semester:</strong> Semester {data.subject.semester}
              </p>
            </div>
          )}
        </div>

        {/* Metric Cards */}
        <div className="lg:col-span-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft">
            <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 uppercase tracking-wider">
              Enrolled Students
            </span>
            <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100 mt-1">
              {totalStudents}
            </p>
            <p className="text-[10px] text-ink-400 dark:text-sand-500">In this semester cohort</p>
          </div>

          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft">
            <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 uppercase tracking-wider">
              Graded Submissions
            </span>
            <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100 mt-1">
              {gradedStudents} / {totalStudents}
            </p>
            <p className="text-[10px] text-ink-400 dark:text-sand-500">Marks entered</p>
          </div>

          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft">
            <span className="text-[11px] font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider flex items-center">
              <AlertTriangle className="w-3 h-3 mr-1" />
              Active Backlogs
            </span>
            <p className="font-display text-2xl font-bold text-rose-600 dark:text-rose-400 mt-1">
              {backlogsCount}
            </p>
            <p className="text-[10px] text-rose-500 dark:text-rose-400/80">Failed / Below 40</p>
          </div>

          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft">
            <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 uppercase tracking-wider">
              Class Attendance
            </span>
            <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100 mt-1">
              {avgAttendance !== null ? `${avgAttendance}%` : 'N/A'}
            </p>
            <p className="text-[10px] text-ink-400 dark:text-sand-500">Subject average</p>
          </div>
        </div>
      </div>

      {/* Grade Sheet Table */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden">
        {/* Table Header & Search */}
        <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <h2 className="font-display text-base font-bold text-ink-900 dark:text-sand-100">
              Grade Sheet &amp; Continuous Assessment
            </h2>
            {data && (
              <span className="text-xs px-2 py-0.5 rounded-md bg-clay-100 dark:bg-charcoal-700 text-clay-700 dark:text-clay-300 font-mono font-bold">
                {data.subject.code}
              </span>
            )}
          </div>

          <div className="relative w-full sm:w-64">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
              <Search className="w-3.5 h-3.5" />
            </div>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search student or PRN..."
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
            />
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-xs text-ink-500 dark:text-sand-400">
            Loading student grade sheet...
          </div>
        ) : !data || filteredStudents.length === 0 ? (
          <div className="p-12 text-center text-xs text-ink-500 dark:text-sand-400">
            No students found in this subject class. Click <strong>Enroll Student</strong> to add students.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-50 dark:bg-charcoal-850 text-ink-500 dark:text-sand-400 border-b border-sand-200 dark:border-charcoal-700">
                <tr>
                  <th className="px-4 py-3 font-semibold">Student & PRN</th>
                  <th className="px-3 py-3 font-semibold text-center w-24">Internal (/50)</th>
                  <th className="px-3 py-3 font-semibold text-center w-24">External (/100)</th>
                  <th className="px-3 py-3 font-semibold text-center w-24">Practical (/50)</th>
                  <th className="px-3 py-3 font-semibold text-center w-24">Assign (/50)</th>
                  <th className="px-3 py-3 font-semibold text-center w-24">Total (/100)</th>
                  <th className="px-3 py-3 font-semibold text-center w-24">Attendance (%)</th>
                  <th className="px-3 py-3 font-semibold text-center w-20">Grade</th>
                  <th className="px-3 py-3 font-semibold text-center w-24">Status</th>
                  <th className="px-4 py-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-200 dark:divide-charcoal-750 text-ink-900 dark:text-sand-100">
                {filteredStudents.map((item) => {
                  const draft = drafts[item.student_id] || {
                    total_marks: 0,
                    attendance: 100,
                    semester: data.subject.semester,
                  };
                  const grade = calculateGradePreview(draft.total_marks);
                  const isBacklog = draft.total_marks < 40 || grade === 'F';
                  const isSaving = savingRowId === item.student_id;

                  return (
                    <tr
                      key={item.student_id}
                      className="hover:bg-sand-50/50 dark:hover:bg-charcoal-750/50 transition-colors"
                    >
                      {/* Student Info */}
                      <td className="px-4 py-3">
                        <div className="font-semibold text-ink-900 dark:text-sand-100">
                          {item.name}
                        </div>
                        <div className="text-[10px] text-ink-400 dark:text-sand-500 font-mono">
                          PRN: {item.erp_id} &bull; Batch: {item.batch}
                        </div>
                      </td>

                      {/* Internal */}
                      <td className="px-3 py-3 text-center">
                        <input
                          type="number"
                          min="0"
                          max="50"
                          step="0.5"
                          value={draft.internal_marks ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              item.student_id,
                              'internal_marks',
                              e.target.value === '' ? null : parseFloat(e.target.value)
                            )
                          }
                          placeholder="-"
                          className="w-16 px-2 py-1 text-center text-xs rounded-lg border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-1 focus:ring-clay-500"
                        />
                      </td>

                      {/* External */}
                      <td className="px-3 py-3 text-center">
                        <input
                          type="number"
                          min="0"
                          max="100"
                          step="0.5"
                          value={draft.external_marks ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              item.student_id,
                              'external_marks',
                              e.target.value === '' ? null : parseFloat(e.target.value)
                            )
                          }
                          placeholder="-"
                          className="w-16 px-2 py-1 text-center text-xs rounded-lg border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-1 focus:ring-clay-500"
                        />
                      </td>

                      {/* Practical */}
                      <td className="px-3 py-3 text-center">
                        <input
                          type="number"
                          min="0"
                          max="50"
                          step="0.5"
                          value={draft.practical_marks ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              item.student_id,
                              'practical_marks',
                              e.target.value === '' ? null : parseFloat(e.target.value)
                            )
                          }
                          placeholder="-"
                          className="w-16 px-2 py-1 text-center text-xs rounded-lg border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-1 focus:ring-clay-500"
                        />
                      </td>

                      {/* Assignment */}
                      <td className="px-3 py-3 text-center">
                        <input
                          type="number"
                          min="0"
                          max="50"
                          step="0.5"
                          value={draft.assignment_marks ?? ''}
                          onChange={(e) =>
                            handleFieldChange(
                              item.student_id,
                              'assignment_marks',
                              e.target.value === '' ? null : parseFloat(e.target.value)
                            )
                          }
                          placeholder="-"
                          className="w-16 px-2 py-1 text-center text-xs rounded-lg border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-1 focus:ring-clay-500"
                        />
                      </td>

                      {/* Total */}
                      <td className="px-3 py-3 text-center">
                        <input
                          type="number"
                          min="0"
                          max="100"
                          step="0.5"
                          value={draft.total_marks}
                          onChange={(e) =>
                            handleFieldChange(
                              item.student_id,
                              'total_marks',
                              parseFloat(e.target.value) || 0
                            )
                          }
                          className="w-16 px-2 py-1 text-center font-bold text-xs rounded-lg border border-sand-300 dark:border-charcoal-700 bg-cream-50 dark:bg-charcoal-800 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-1 focus:ring-clay-500"
                        />
                      </td>

                      {/* Attendance */}
                      <td className="px-3 py-3 text-center">
                        <input
                          type="number"
                          min="0"
                          max="100"
                          step="1"
                          value={draft.attendance}
                          onChange={(e) =>
                            handleFieldChange(
                              item.student_id,
                              'attendance',
                              parseFloat(e.target.value) || 0
                            )
                          }
                          className={`w-16 px-2 py-1 text-center text-xs rounded-lg border font-semibold ${
                            draft.attendance < 75
                              ? 'border-rose-300 text-rose-600 bg-rose-50 dark:bg-rose-950/20'
                              : 'border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100'
                          } focus:outline-none focus:ring-1 focus:ring-clay-500`}
                        />
                      </td>

                      {/* Grade Badge */}
                      <td className="px-3 py-3 text-center">
                        <span
                          className={`inline-block w-7 py-0.5 text-center rounded text-xs font-bold ${
                            grade === 'F'
                              ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
                              : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400'
                          }`}
                        >
                          {grade}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="px-3 py-3 text-center">
                        {isBacklog ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-400">
                            Backlog
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400">
                            Pass
                          </span>
                        )}
                      </td>

                      {/* Action */}
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleSaveMarks(item.student_id)}
                          disabled={isSaving}
                          className="inline-flex items-center px-3 py-1.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift disabled:opacity-50 transition-all"
                        >
                          <Save className="w-3.5 h-3.5 mr-1" />
                          {isSaving ? 'Saving...' : 'Save'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Enroll Student (Section 9) */}
      {isAddStudentModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-charcoal-900/60 backdrop-blur-sm animate-fade-in overflow-y-auto">
          <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 shadow-2xl w-full max-w-2xl my-8 overflow-hidden animate-scale-up">
            <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between bg-cream-50 dark:bg-charcoal-850">
              <div>
                <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 flex items-center">
                  <UserPlus className="w-5 h-5 mr-2 text-clay-500" />
                  Section 9: Teacher &rarr; Enroll Student
                </h3>
                <p className="text-[11px] text-ink-500 dark:text-sand-400">
                  Enrolling student under your mentorship ({user?.first_name || 'Teacher'}) and assigning to your department cohort.
                </p>
              </div>
              <button
                onClick={() => setIsAddStudentModalOpen(false)}
                className="text-ink-400 hover:text-ink-600 dark:hover:text-sand-200 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddStudentSubmit} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto">
              <h4 className="text-xs font-bold uppercase tracking-wider text-clay-600 dark:text-clay-400">
                1. Personal Information
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={studentForm.name}
                    onChange={(e) => setStudentForm({ ...studentForm, name: e.target.value })}
                    placeholder="e.g. Rahul Sharma"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300">
                      Student ID / PRN
                    </label>
                    <span className="inline-flex items-center gap-1 text-[10px] text-emerald-700 dark:text-emerald-400 font-medium bg-emerald-50 dark:bg-emerald-950/50 px-1.5 py-0.5 rounded border border-emerald-200 dark:border-emerald-800/40">
                      <Sparkles className="w-2.5 h-2.5 text-emerald-600 dark:text-emerald-400" />
                      Auto-generated
                    </span>
                  </div>
                  <div className="relative">
                    <input
                      type="text"
                      value={studentForm.erp_id || ''}
                      onChange={(e) => setStudentForm({ ...studentForm, erp_id: e.target.value.toUpperCase() })}
                      placeholder="Auto-generated on submit"
                      className="w-full pl-3 pr-8 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50 uppercase font-mono"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        fetchTeacherNextErp(
                          studentForm.department,
                          studentForm.batch,
                          studentForm.admission_year
                        )
                      }
                      title="Regenerate next available Enrollment ID"
                      className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-ink-400 hover:text-clay-600 dark:hover:text-sand-200 transition-colors"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <p className="mt-1 text-[10px] text-ink-400 dark:text-sand-400">
                    Leave blank to automatically assign the next available ID.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={studentForm.email}
                    onChange={(e) => setStudentForm({ ...studentForm, email: e.target.value })}
                    placeholder="rahul.sharma@university.edu"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Phone Number
                  </label>
                  <input
                    type="text"
                    value={studentForm.phone}
                    onChange={(e) => setStudentForm({ ...studentForm, phone: e.target.value })}
                    placeholder="+91 9876543210"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Date of Birth
                  </label>
                  <input
                    type="date"
                    value={studentForm.dob}
                    onChange={(e) => setStudentForm({ ...studentForm, dob: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Gender
                  </label>
                  <select
                    value={studentForm.gender}
                    onChange={(e) => setStudentForm({ ...studentForm, gender: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <h4 className="text-xs font-bold uppercase tracking-wider text-clay-600 dark:text-clay-400 pt-2 border-t border-sand-200 dark:border-charcoal-700">
                2. Academic Information
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Department *
                  </label>
                  <input
                    type="text"
                    required
                    value={studentForm.department}
                    onChange={(e) => setStudentForm({ ...studentForm, department: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Course / Degree
                  </label>
                  <input
                    type="text"
                    value={studentForm.course}
                    onChange={(e) => setStudentForm({ ...studentForm, course: e.target.value })}
                    placeholder="B.Tech"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Semester *
                  </label>
                  <select
                    value={studentForm.semester}
                    onChange={(e) => setStudentForm({ ...studentForm, semester: parseInt(e.target.value, 10) })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
                      <option key={s} value={s}>
                        Semester {s}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Batch
                  </label>
                  <input
                    type="text"
                    value={studentForm.batch}
                    onChange={(e) => setStudentForm({ ...studentForm, batch: e.target.value })}
                    placeholder="2022-26"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Division / Section
                  </label>
                  <input
                    type="text"
                    value={studentForm.division}
                    onChange={(e) => setStudentForm({ ...studentForm, division: e.target.value })}
                    placeholder="A"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Admission Year
                  </label>
                  <input
                    type="text"
                    value={studentForm.admission_year}
                    onChange={(e) => setStudentForm({ ...studentForm, admission_year: e.target.value })}
                    placeholder="2022"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-sand-200 dark:border-charcoal-700">
                <h4 className="text-xs font-bold uppercase tracking-wider text-clay-600 dark:text-clay-400 flex items-center">
                  <Lock className="w-3.5 h-3.5 mr-1" />
                  3. Student Portal Access & Authorization (Optional)
                </h4>
                <button
                  type="button"
                  onClick={() =>
                    setStudentForm({
                      ...studentForm,
                      password: 'StudentPass@123',
                      confirm_password: 'StudentPass@123',
                      authorize_account: true,
                    })
                  }
                  className="text-[10px] font-semibold text-clay-600 dark:text-clay-400 hover:underline flex items-center gap-1"
                >
                  <Key className="w-2.5 h-2.5" />
                  Use default (StudentPass@123)
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Login Password
                  </label>
                  <div className="relative">
                    <input
                      type={showStudentPassword ? 'text' : 'password'}
                      value={studentForm.password}
                      onChange={(e) => setStudentForm({ ...studentForm, password: e.target.value })}
                      placeholder="Leave blank to skip portal account"
                      className="w-full pl-3 pr-10 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                    />
                    <button
                      type="button"
                      onClick={() => setShowStudentPassword(!showStudentPassword)}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-ink-400 hover:text-ink-600 dark:hover:text-sand-200 transition-colors"
                    >
                      {showStudentPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Confirm Password
                  </label>
                  <input
                    type={showStudentPassword ? 'text' : 'password'}
                    value={studentForm.confirm_password}
                    onChange={(e) => setStudentForm({ ...studentForm, confirm_password: e.target.value })}
                    placeholder="Re-enter password"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              {/* Authorize checkbox */}
              {studentForm.password && (
                <div className="p-3 bg-sand-50/80 dark:bg-charcoal-800/60 rounded-xl border border-sand-200 dark:border-charcoal-700">
                  <label className="flex items-start gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={studentForm.authorize_account !== false}
                      onChange={(e) => setStudentForm({ ...studentForm, authorize_account: e.target.checked })}
                      className="w-4 h-4 mt-0.5 rounded text-emerald-600 focus:ring-emerald-500 border-sand-300 dark:border-charcoal-700"
                    />
                    <div>
                      <span className="text-xs font-semibold text-ink-800 dark:text-sand-200 flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                        Authorize Account Immediately (Active & Email Verified)
                      </span>
                      <span className="text-[10px] text-ink-400 dark:text-sand-400 block mt-0.5">
                        Student will be able to log in to Beacon immediately using their email and this password without email verification code.
                      </span>
                    </div>
                  </label>
                </div>
              )}

              <div className="pt-4 flex items-center justify-end space-x-3 border-t border-sand-200 dark:border-charcoal-700">
                <button
                  type="button"
                  onClick={() => setIsAddStudentModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-ink-600 dark:text-sand-300 hover:bg-sand-100 dark:hover:bg-charcoal-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addingStudent}
                  className="px-5 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift disabled:opacity-50"
                >
                  {addingStudent ? 'Enrolling...' : 'Enroll & Assign to My Cohort'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
