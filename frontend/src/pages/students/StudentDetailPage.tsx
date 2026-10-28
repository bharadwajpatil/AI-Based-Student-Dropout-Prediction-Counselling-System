import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { studentApi } from '../../api/students';
import { counsellingApi } from '../../api/counselling';
import { marksApi, type SubjectMarks, type StudentBacklogSummary } from '../../api/marks';
import { chatbotApi, type StudyPlanResponse } from '../../api/chatbot';
import type { Student, PerformanceRecord, RiskAssessment, CounsellingCase } from '../../types';
import { RiskBadge } from '../../components/common/RiskBadge';
import { FactorBreakdown } from '../../components/students/FactorRadarChart';
import { PerformanceModal } from '../../components/students/PerformanceModal';
import { AssignMentorModal } from '../../components/students/AssignMentorModal';
import { AiRecommendationCard } from '../../components/counselling/AiRecommendationCard';
import { CaseTimeline } from '../../components/counselling/CaseTimeline';
import { CrisisBanner } from '../../components/counselling/CrisisBanner';
import { Skeleton } from '../../components/common/Skeleton';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type { FacultyMember } from '../../api/students';
import {
  ArrowLeft,
  HeartHandshake,
  Edit3,
  Bookmark,
  Download,
  Info,
  UserCheck,
  Users,
  BookOpen,
  Calendar,
  AlertTriangle,
} from 'lucide-react';

export const StudentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { hasRole } = useAuth();
  const { success, error } = useToast();

  const [student, setStudent] = useState<Student | null>(null);
  const [performances, setPerformances] = useState<PerformanceRecord[]>([]);
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [counsellingCase, setCounsellingCase] = useState<CounsellingCase | null>(null);
  const [subjectMarks, setSubjectMarks] = useState<SubjectMarks[]>([]);
  const [backlogSummary, setBacklogSummary] = useState<StudentBacklogSummary | null>(null);
  const [studyPlan, setStudyPlan] = useState<StudyPlanResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [perfModalOpen, setPerfModalOpen] = useState<boolean>(false);
  const [editingPerf, setEditingPerf] = useState<PerformanceRecord | null>(null);
  const [assignModalOpen, setAssignModalOpen] = useState<boolean>(false);
  const [facultyMap, setFacultyMap] = useState<Record<string, FacultyMember>>({});
  const [activeTab, setActiveTab] = useState<'overview' | 'counselling' | 'marks' | 'study_plan'>('overview');

  const loadData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const st = await studentApi.getStudent(id);
      setStudent(st);

      const perfs = await studentApi.getPerformance(id);
      setPerformances(perfs);

      try {
        const r = await studentApi.getRisk(id);
        setRisk(r);
      } catch {
        // May not have computed risk yet
      }

      try {
        const facList = await studentApi.listFaculty();
        const fMap: Record<string, FacultyMember> = {};
        facList.forEach((f) => {
          fMap[f.id] = f;
        });
        setFacultyMap(fMap);
      } catch {
        // Non-critical if fails
      }

      if (hasRole(['admin', 'hod', 'teacher'])) {
        try {
          const cCase = await counsellingApi.getStudentCase(id);
          setCounsellingCase(cCase);
        } catch {
          // No counselling case exists yet
        }
      }

      // Load curriculum marks, backlogs, and study plan
      try {
        const [sm, bs, sp] = await Promise.all([
          marksApi.getStudentMarks(id),
          marksApi.getStudentBacklogs(id),
          chatbotApi.getStudyPlan(id).catch(() => null),
        ]);
        setSubjectMarks(sm);
        setBacklogSummary(bs);
        setStudyPlan(sp);
      } catch (marksErr) {
        console.error('Failed to load marks or study plan', marksErr);
      }
    } catch (err) {
      console.error('Failed to load student details', err);
    } finally {
      setLoading(false);
    }
  }, [hasRole, id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleGenerateAi = async (notes?: string) => {
    if (!id) return;
    try {
      const updatedCase = await counsellingApi.generateRecommendation(id, {
        teacher_notes: notes,
        force_regenerate: true,
      });
      setCounsellingCase(updatedCase);
      success('Intervention Plan Generated', 'Personalized recommendations created.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Generation failed';
      error('Failed to Generate', msg);
    }
  };

  const handleAddNote = async (content: string) => {
    if (!counsellingCase) return;
    try {
      const updated = await counsellingApi.addNote(counsellingCase.id, content);
      setCounsellingCase(updated);
      success('Note Recorded', 'Chronological meeting notes updated.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to add note';
      error('Failed to Save', msg);
    }
  };

  const handleExportData = async () => {
    if (!id) return;
    try {
      const data = await studentApi.exportData(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `student_export_${student?.erp_id || id}.json`;
      a.click();
      URL.revokeObjectURL(url);
      success('Export Complete', 'Student privacy record export downloaded.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      error('Export Failed', msg);
    }
  };

  if (loading && !student) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="h-64 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl lg:col-span-2" />
        </div>
      </div>
    );
  }

  if (!student) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center">
        <p className="text-sm font-semibold text-ink-900 dark:text-sand-100">Student not found.</p>
        <Link to="/students" className="mt-4 inline-block text-xs font-semibold text-clay-500">
          Back to Students
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-up">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <Link
          to="/students"
          className="inline-flex items-center text-xs font-semibold text-ink-600 dark:text-sand-400 hover:text-clay-500 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to Student Roster
        </Link>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleExportData}
            title="Download FERPA / India DPDP Article 11 Data Portability Export"
            className="inline-flex items-center px-3.5 py-2 rounded-xl bg-white dark:bg-charcoal-700 hover:bg-sand-100 dark:hover:bg-charcoal-600 text-ink-700 dark:text-sand-200 border border-sand-300 dark:border-charcoal-600 text-xs font-semibold shadow-soft card-lift transition-all"
          >
            <Download className="w-3.5 h-3.5 mr-1.5 text-clay-500" /> Export Records
          </button>

          {hasRole(['admin', 'hod']) && (
            <button
              onClick={() => setAssignModalOpen(true)}
              className="inline-flex items-center px-3.5 py-2 rounded-xl bg-white dark:bg-charcoal-700 hover:bg-sand-100 dark:hover:bg-charcoal-600 text-ink-700 dark:text-sand-200 border border-sand-300 dark:border-charcoal-600 text-xs font-semibold shadow-soft card-lift transition-all"
            >
              <UserCheck className="w-3.5 h-3.5 mr-1.5 text-clay-500" /> Assign Faculty
            </button>
          )}

          {hasRole(['admin', 'hod', 'teacher']) && (
            <button
              onClick={() => {
                setEditingPerf(null);
                setPerfModalOpen(true);
              }}
              className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
            >
              <Edit3 className="w-3.5 h-3.5 mr-1.5" /> Enter / Update Performance
            </button>
          )}
        </div>
      </div>

      {/* Header Profile Card */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-6 sm:p-8 shadow-soft">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6 pb-6 border-b border-sand-200 dark:border-charcoal-700">
          <div className="flex items-start space-x-4">
            <div className="w-14 h-14 rounded-2xl bg-cream-100 dark:bg-charcoal-750 text-clay-500 flex items-center justify-center font-display font-bold text-xl shadow-soft">
              {student.name.charAt(0)}
            </div>
            <div>
              <div className="flex items-center space-x-3">
                <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100">
                  {student.name}
                </h1>
                <RiskBadge
                  level={risk?.level || student.current_risk?.level || 'Insufficient Data'}
                  isEscalated={risk?.level === 'High'}
                  size="md"
                />
              </div>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-500 dark:text-sand-400">
                <span>
                  ERP ID: <strong className="font-mono text-ink-900 dark:text-sand-200">{student.erp_id}</strong>
                </span>
                <span>•</span>
                <span>Department: {student.department}</span>
                <span>•</span>
                <span>Current Semester: Sem {student.semester}</span>
                <span>•</span>
                <span>Batch: {student.batch}</span>
              </div>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="flex items-center space-x-4 bg-cream-50 dark:bg-charcoal-750 p-4 rounded-xl border border-sand-200 dark:border-charcoal-700 text-center">
            <div>
              <p className="text-[10px] uppercase font-semibold text-ink-500 dark:text-sand-400">
                Risk Score
              </p>
              <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100">
                {risk?.score !== null && risk?.score !== undefined ? `${risk.score.toFixed(1)}%` : 'N/A'}
              </p>
            </div>
            <div className="w-px h-8 bg-sand-300 dark:bg-charcoal-600" />
            <div>
              <p className="text-[10px] uppercase font-semibold text-ink-500 dark:text-sand-400">
                Confidence
              </p>
              <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100">
                {risk?.confidence ? `${Math.round(risk.confidence * 100)}%` : '—'}
              </p>
            </div>
          </div>
        </div>

        {/* Dedicated Assigned Faculty Mentors Banner */}
        <div className="mt-4 p-3.5 rounded-xl bg-sand-50 dark:bg-charcoal-750 border border-sand-200 dark:border-charcoal-700 flex flex-wrap items-center justify-between gap-3 shadow-xs">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-semibold text-ink-700 dark:text-sand-200 flex items-center">
              <Users className="w-4 h-4 mr-1.5 text-clay-500" />
              Assigned Faculty Mentors:
            </span>
            {student.assigned_teacher_ids && student.assigned_teacher_ids.length > 0 ? (
              student.assigned_teacher_ids.map((tid) => (
                <span
                  key={tid}
                  className="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold bg-white dark:bg-charcoal-800 text-ink-900 dark:text-sand-100 border border-sand-300 dark:border-charcoal-600 shadow-xs"
                >
                  👨‍🏫 {facultyMap[tid]?.name || tid}
                  {facultyMap[tid]?.email && (
                    <span className="ml-1 text-[11px] text-ink-500 dark:text-sand-400 font-normal">
                      ({facultyMap[tid].email})
                    </span>
                  )}
                </span>
              ))
            ) : (
              <span className="text-amber-600 dark:text-amber-400 text-xs font-semibold">
                ⚠️ No faculty mentor assigned yet
              </span>
            )}
          </div>

          {hasRole(['admin', 'hod']) && (
            <button
              onClick={() => setAssignModalOpen(true)}
              className="inline-flex items-center px-3.5 py-1.5 rounded-lg bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft transition-all"
            >
              <UserCheck className="w-3.5 h-3.5 mr-1.5" />
              Assign / Change Faculty
            </button>
          )}
        </div>

        {/* Ethical Decision Support Advisory */}
        <div className="mt-4 px-3.5 py-2.5 rounded-xl bg-sand-100/70 dark:bg-charcoal-750 border border-sand-300/80 dark:border-charcoal-600 flex items-center text-xs text-ink-600 dark:text-sand-300">
          <Info className="w-4 h-4 mr-2.5 text-clay-500 shrink-0" />
          <span>
            <strong>Decision Support Notice:</strong> Risk scores and factor breakdowns are advisory decision-support aids for faculty mentorship. They do not constitute automated academic determinations.
          </span>
        </div>

        {/* Tab Navigation */}
        <div className="flex space-x-4 pt-4 border-b border-sand-200 dark:border-charcoal-700">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-3 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'overview'
                ? 'border-clay-500 text-clay-600 dark:text-clay-400'
                : 'border-transparent text-ink-500 dark:text-sand-400 hover:text-ink-900'
            }`}
          >
            Academic Assessment & Trajectory
          </button>
          {hasRole(['admin', 'hod', 'teacher']) && (
            <button
              onClick={() => setActiveTab('counselling')}
              className={`pb-3 text-xs font-semibold border-b-2 transition-all flex items-center ${
                activeTab === 'counselling'
                  ? 'border-clay-500 text-clay-600 dark:text-clay-400'
                  : 'border-transparent text-ink-500 dark:text-sand-400 hover:text-ink-900'
              }`}
            >
              <HeartHandshake className="w-3.5 h-3.5 mr-1.5" /> Mentorship & AI Intervention
              {counsellingCase && (
                <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-cream-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 capitalize">
                  {counsellingCase.status}
                </span>
              )}
            </button>
          )}

          <button
            onClick={() => setActiveTab('marks')}
            className={`pb-3 text-xs font-semibold border-b-2 transition-all flex items-center ${
              activeTab === 'marks'
                ? 'border-clay-500 text-clay-600 dark:text-clay-400'
                : 'border-transparent text-ink-500 dark:text-sand-400 hover:text-ink-900'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5 mr-1.5" /> Subject Marks &amp; Backlogs ({subjectMarks.length})
            {backlogSummary && backlogSummary.backlog_count > 0 && (
              <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400">
                {backlogSummary.backlog_count}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('study_plan')}
            className={`pb-3 text-xs font-semibold border-b-2 transition-all flex items-center ${
              activeTab === 'study_plan'
                ? 'border-clay-500 text-clay-600 dark:text-clay-400'
                : 'border-transparent text-ink-500 dark:text-sand-400 hover:text-ink-900'
            }`}
          >
            <Calendar className="w-3.5 h-3.5 mr-1.5" /> 7-Day AI Study Plan
          </button>
        </div>
      </div>

      {/* OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Factor Breakdown Column */}
          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
                Risk Contributing Factors
              </h3>
              {risk?.watchlist && (
                <span className="flex items-center text-[10px] font-bold text-amber-600 bg-amber-50 dark:bg-amber-600/10 px-2 py-0.5 rounded-full">
                  <Bookmark className="w-3 h-3 mr-1" /> Watchlist
                </span>
              )}
            </div>
            <p className="text-xs text-ink-500 dark:text-sand-400 leading-relaxed">
              Factor contribution to the final risk score calculated via the deterministic multi-parameter engine.
            </p>

            <FactorBreakdown factors={risk?.factors || []} />

            {risk?.overrides_applied && risk.overrides_applied.length > 0 && (
              <div className="pt-3 border-t border-sand-200 dark:border-charcoal-700">
                <p className="text-[10px] font-semibold uppercase text-ink-500 dark:text-sand-400 mb-1">
                  Deterministic Override Rules
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {risk.overrides_applied.map((rule) => (
                    <span
                      key={rule}
                      className="text-[10px] font-mono px-2 py-0.5 rounded bg-sand-200 dark:bg-charcoal-700 text-ink-800 dark:text-sand-300"
                    >
                      {rule}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Academic History Column */}
          <div className="lg:col-span-2 bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden">
            <div className="p-6 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between">
              <div>
                <h3 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
                  Semester Performance History
                </h3>
                <p className="text-xs text-ink-500 dark:text-sand-400">
                  Validated academic records with optimistic concurrency versioning.
                </p>
              </div>
            </div>

            {performances.length === 0 ? (
              <div className="p-8 text-center text-xs text-ink-500 dark:text-sand-400">
                No semester performance records entered yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-cream-50 dark:bg-charcoal-750 text-ink-600 dark:text-sand-400 uppercase font-semibold">
                    <tr>
                      <th className="px-5 py-3">Semester</th>
                      <th className="px-5 py-3">Academic Year</th>
                      <th className="px-5 py-3">Attendance</th>
                      <th className="px-5 py-3">Marks</th>
                      <th className="px-5 py-3">Backlogs</th>
                      <th className="px-5 py-3">Assignments</th>
                      <th className="px-5 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-sand-200 dark:divide-charcoal-700 text-ink-900 dark:text-sand-100">
                    {performances.map((p) => (
                      <tr
                        key={p.semester}
                        className="hover:bg-cream-50/50 dark:hover:bg-charcoal-750/50 transition-colors"
                      >
                        <td className="px-5 py-3.5 font-semibold">Semester {p.semester}</td>
                        <td className="px-5 py-3.5 text-ink-500 dark:text-sand-400">
                          {p.academic_year}
                        </td>
                        <td className="px-5 py-3.5">
                          <span
                            className={`font-semibold ${
                              p.attendance < 50
                                ? 'text-rose-600'
                                : p.attendance < 75
                                ? 'text-amber-600'
                                : 'text-sage-600'
                            }`}
                          >
                            {p.attendance.toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-5 py-3.5 font-semibold">
                          {p.marks !== null && p.marks !== undefined ? `${p.marks.toFixed(1)}%` : '—'}
                        </td>
                        <td className="px-5 py-3.5">
                          <span
                            className={
                              (p.backlogs || 0) > 0 ? 'text-rose-600 font-semibold' : 'text-ink-600'
                            }
                          >
                            {p.backlogs || 0}
                          </span>
                        </td>
                        <td className="px-5 py-3.5">
                          {p.assignments !== null && p.assignments !== undefined
                            ? `${p.assignments.toFixed(1)}%`
                            : '—'}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          {hasRole(['admin', 'hod', 'teacher']) && (
                            <button
                              onClick={() => {
                                setEditingPerf(p);
                                setPerfModalOpen(true);
                              }}
                              className="px-2.5 py-1 rounded-lg bg-cream-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 font-semibold hover:bg-clay-500 hover:text-white transition-all"
                            >
                              Edit
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* COUNSELLING TAB */}
      {activeTab === 'counselling' && hasRole(['admin', 'hod', 'teacher']) && (
        <div className="space-y-6 animate-fade-up">
          {/* Crisis Banner if triggered */}
          {counsellingCase && (
            <CrisisBanner
              escalateToHod={counsellingCase.escalate_to_hod}
              referToCounsellor={counsellingCase.refer_to_counsellor}
            />
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <AiRecommendationCard
              recommendation={counsellingCase?.ai_recommendation}
              onRegenerate={handleGenerateAi}
            />

            <CaseTimeline
              notes={counsellingCase?.notes_timeline || []}
              onAddNote={handleAddNote}
            />
          </div>
        </div>
      )}

      {/* SUBJECT MARKS & BACKLOGS TAB */}
      {activeTab === 'marks' && (
        <div className="space-y-6 animate-fade-up">
          {/* Backlog Alert if any */}
          {backlogSummary && backlogSummary.backlog_count > 0 && (
            <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/50 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <AlertTriangle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />
                <span className="text-xs font-semibold text-rose-800 dark:text-rose-200">
                  {backlogSummary.backlog_count} Active Backlog(s): {backlogSummary.backlog_subjects.map((b) => `${b.subject_name} (${b.total_marks}/100)`).join(', ')}
                </span>
              </div>
            </div>
          )}

          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden">
            <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between">
              <h3 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100 flex items-center">
                <BookOpen className="w-4 h-4 mr-2 text-clay-500" />
                Curriculum Subject Continuous Assessment
              </h3>
              <span className="text-xs text-ink-500 dark:text-sand-400">
                {subjectMarks.length} courses recorded
              </span>
            </div>

            {subjectMarks.length === 0 ? (
              <div className="p-8 text-center text-xs text-ink-500 dark:text-sand-400">
                No subject marks recorded yet for this student.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-cream-50 dark:bg-charcoal-850 text-ink-500 dark:text-sand-400 border-b border-sand-200 dark:border-charcoal-700">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Subject</th>
                      <th className="px-3 py-3 font-semibold text-center">Internal (/50)</th>
                      <th className="px-3 py-3 font-semibold text-center">External (/100)</th>
                      <th className="px-3 py-3 font-semibold text-center">Practical (/50)</th>
                      <th className="px-3 py-3 font-semibold text-center">Assign (/50)</th>
                      <th className="px-3 py-3 font-semibold text-center">Total (/100)</th>
                      <th className="px-3 py-3 font-semibold text-center">Attendance</th>
                      <th className="px-3 py-3 font-semibold text-center">Grade</th>
                      <th className="px-3 py-3 font-semibold text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-sand-200 dark:divide-charcoal-750 text-ink-900 dark:text-sand-100">
                    {subjectMarks.map((m) => (
                      <tr key={m.id} className="hover:bg-sand-50/50 dark:hover:bg-charcoal-750/50">
                        <td className="px-4 py-3">
                          <span className="font-semibold">{m.subject_name}</span>
                          <span className="block text-[10px] text-ink-400 font-mono">{m.subject_code} (Sem {m.semester})</span>
                        </td>
                        <td className="px-3 py-3 text-center">{m.internal_marks ?? '-'}</td>
                        <td className="px-3 py-3 text-center">{m.external_marks ?? '-'}</td>
                        <td className="px-3 py-3 text-center">{m.practical_marks ?? '-'}</td>
                        <td className="px-3 py-3 text-center">{m.assignment_marks ?? '-'}</td>
                        <td className="px-3 py-3 text-center font-bold">{m.total_marks}/100</td>
                        <td className={`px-3 py-3 text-center font-semibold ${m.attendance < 75 ? 'text-rose-600' : ''}`}>{m.attendance}%</td>
                        <td className="px-3 py-3 text-center">
                          <span className={`inline-block w-6 py-0.5 text-center rounded text-xs font-bold ${m.grade === 'F' ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-800'}`}>
                            {m.grade}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-center">
                          {m.is_backlog ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-400">
                              Backlog
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400">
                              Pass
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 7-DAY AI STUDY PLAN TAB */}
      {activeTab === 'study_plan' && (
        <div className="space-y-6 animate-fade-up">
          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft">
            <h3 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100 flex items-center">
              <Calendar className="w-4 h-4 mr-2 text-clay-500" />
              Section 17: 7-Day Personalized Schedule &amp; Backlog Clearance
            </h3>
            <p className="text-xs text-ink-500 dark:text-sand-400 mt-1">
              Active weak areas: {studyPlan?.weak_areas?.join(', ') || 'Core coursework'}.
            </p>

            {studyPlan?.weekly_schedule ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
                {Object.entries(studyPlan.weekly_schedule).map(([day, slots]) => (
                  <div key={day} className="p-4 rounded-xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700 space-y-2">
                    <div className="flex items-center justify-between pb-1 border-b border-sand-200 dark:border-charcoal-700">
                      <span className="font-bold text-xs capitalize text-ink-900 dark:text-sand-100">{day}</span>
                      <span className="text-[10px] text-clay-600 font-semibold">{slots.reduce((a, s) => a + s.hours, 0)} hrs</span>
                    </div>
                    {slots.map((s, idx) => (
                      <div key={idx} className="text-xs">
                        <span className="font-semibold text-ink-800 dark:text-sand-200">{s.subject}</span>
                        <span className="text-ink-400 text-[10px]"> ({s.hours} hrs) - {s.activity}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-ink-500 dark:text-sand-400">
                No study plan generated yet for this student.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Performance Edit Modal */}
      <PerformanceModal
        isOpen={perfModalOpen}
        onClose={() => setPerfModalOpen(false)}
        studentId={student.id}
        studentName={student.name}
        existingPerformance={editingPerf}
        onSaved={loadData}
      />

      {/* Assign Mentor Modal */}
      {student && (
        <AssignMentorModal
          isOpen={assignModalOpen}
          onClose={() => setAssignModalOpen(false)}
          student={student}
          onAssigned={(updated) => {
            setStudent(updated);
            loadData();
          }}
        />
      )}
    </div>
  );
};
