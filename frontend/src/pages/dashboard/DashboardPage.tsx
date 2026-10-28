import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { analyticsApi } from '../../api/analytics';
import { studentApi } from '../../api/students';
import { adminApi, type AdminStats } from '../../api/admin';
import { hodApi, type HodStats } from '../../api/hod';
import { subjectApi, type SubjectItem } from '../../api/subjects';
import { StudentPortalPage } from '../student/StudentPortalPage';
import type { AnalyticsOverview, Student } from '../../types';
import { KpiCard } from '../../components/common/KpiCard';
import { RiskBadge } from '../../components/common/RiskBadge';
import { SkeletonTable } from '../../components/common/Skeleton';
import { ImportModal } from '../../components/students/ImportModal';
import { useRealtime } from '../../hooks/useRealtime';
import {
  Users,
  ShieldAlert,
  Clock,
  FileSpreadsheet,
  ArrowRight,
  Shield,
  BookOpen,
  ClipboardList,
  GraduationCap,
  AlertTriangle,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user, hasRole } = useAuth();

  // If student is logged in, immediately show their dedicated self-service portal
  if (hasRole('student')) {
    return <StudentPortalPage />;
  }

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [hodStats, setHodStats] = useState<HodStats | null>(null);
  const [teacherSubjects, setTeacherSubjects] = useState<SubjectItem[]>([]);
  const [highRiskStudents, setHighRiskStudents] = useState<Student[]>([]);
  const [assignedStudents, setAssignedStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [importModalOpen, setImportModalOpen] = useState<boolean>(false);
  const [selectedDept, setSelectedDept] = useState<string>('');

  const loadData = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      if (hasRole('admin')) {
        const [ov, aStats, studentsRes] = await Promise.all([
          analyticsApi.getOverview(selectedDept || undefined),
          adminApi.getStats().catch(() => null),
          studentApi.listStudents({
            level: 'High',
            limit: 5,
            department: selectedDept || undefined,
          }),
        ]);
        setOverview(ov);
        setAdminStats(aStats);
        setHighRiskStudents(studentsRes.items);
      } else if (hasRole('hod')) {
        const [ov, hStats, studentsRes] = await Promise.all([
          analyticsApi.getOverview(user?.department || undefined),
          hodApi.getStats().catch(() => null),
          studentApi.listStudents({
            level: 'High',
            limit: 5,
            department: user?.department || undefined,
          }),
        ]);
        setOverview(ov);
        setHodStats(hStats);
        setHighRiskStudents(studentsRes.items);
      } else if (hasRole('teacher')) {
        const [ov, studentsRes, mySubs] = await Promise.all([
          analyticsApi.getOverview(),
          studentApi.listStudents({ limit: 10 }),
          subjectApi.getMyAssignedSubjects().catch(() => []),
        ]);
        setOverview(ov);
        setAssignedStudents(studentsRes.items);
        setTeacherSubjects(mySubs);
      }
    } catch (err) {
      console.error('Failed to load dashboard metrics', err);
    } finally {
      setLoading(false);
    }
  }, [hasRole, selectedDept, user]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Real-time listener: refresh overview when risk changes
  useRealtime({
    onRiskChanged: () => {
      loadData();
    },
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-up">
      {/* Top Banner & Quick Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-sand-200 dark:border-charcoal-800">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink-900 dark:text-sand-100">
            {hasRole('admin')
              ? 'Institutional Governance & Academic Early Warning'
              : hasRole('hod')
              ? `Departmental Command Center — ${user?.department || 'Department'}`
              : `Faculty Mentorship & Grading Hub`}
          </h1>
          <p className="text-xs sm:text-sm text-ink-500 dark:text-sand-400 mt-1">
            {hasRole('admin')
              ? 'Campus-wide risk tracking, HOD oversight, faculty intervention, and predictive retention metrics.'
              : hasRole('hod')
              ? `Curriculum subjects, teaching assignments, and student dropout-risk monitoring for ${user?.department || 'your department'}.`
              : 'Your assigned subjects, continuous marks entry, and direct student cohort monitoring.'}
          </p>
        </div>

        {hasRole(['admin', 'hod']) && (
          <div className="flex items-center space-x-3">
            {hasRole('admin') && (
              <select
                value={selectedDept}
                onChange={(e) => setSelectedDept(e.target.value)}
                className="px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs font-medium text-ink-900 dark:text-sand-100"
              >
                <option value="">All Departments</option>
                <option value="Computer Science">Computer Science</option>
                <option value="Information Technology">Information Technology</option>
                <option value="Electronics & Telecommunication">Electronics & Telecommunication</option>
                <option value="Mechanical Engineering">Mechanical Engineering</option>
                <option value="Civil Engineering">Civil Engineering</option>
              </select>
            )}

            <button
              onClick={() => setImportModalOpen(true)}
              className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
            >
              <FileSpreadsheet className="w-4 h-4 mr-1.5" /> Bulk Import
            </button>
          </div>
        )}
      </div>

      {/* ADMIN VIEW (Section 2 & 4) */}
      {hasRole('admin') && (
        <div className="space-y-8">
          {/* Quick Shortcuts */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Link
              to="/admin/hods"
              className="p-4 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center space-x-3 group"
            >
              <div className="w-10 h-10 rounded-xl bg-clay-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 flex items-center justify-center group-hover:bg-clay-500 group-hover:text-white transition-all">
                <Shield className="w-5 h-5" />
              </div>
              <div>
                <span className="font-display font-bold text-sm text-ink-900 dark:text-sand-100 block">
                  HOD Governance
                </span>
                <span className="text-[11px] text-ink-400 dark:text-sand-500">
                  Manage department heads
                </span>
              </div>
            </Link>

            <Link
              to="/faculty"
              className="p-4 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center space-x-3 group"
            >
              <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-all">
                <GraduationCap className="w-5 h-5" />
              </div>
              <div>
                <span className="font-display font-bold text-sm text-ink-900 dark:text-sand-100 block">
                  Faculty Roster
                </span>
                <span className="text-[11px] text-ink-400 dark:text-sand-500">
                  Inspect teaching staff
                </span>
              </div>
            </Link>

            <Link
              to="/hod/subjects"
              className="p-4 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center space-x-3 group"
            >
              <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center group-hover:bg-emerald-600 group-hover:text-white transition-all">
                <BookOpen className="w-5 h-5" />
              </div>
              <div>
                <span className="font-display font-bold text-sm text-ink-900 dark:text-sand-100 block">
                  Curriculum Courses
                </span>
                <span className="text-[11px] text-ink-400 dark:text-sand-500">
                  Subject allocations
                </span>
              </div>
            </Link>

            <Link
              to="/analytics"
              className="p-4 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center space-x-3 group"
            >
              <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 flex items-center justify-center group-hover:bg-amber-600 group-hover:text-white transition-all">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <span className="font-display font-bold text-sm text-ink-900 dark:text-sand-100 block">
                  Retention Reports
                </span>
                <span className="text-[11px] text-ink-400 dark:text-sand-500">
                  Predictive risk stats
                </span>
              </div>
            </Link>
          </div>

          {/* Admin KPI Summary Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
            <KpiCard
              title="Total HODs"
              value={adminStats?.total_hods ?? 0}
              subtitle="Department heads"
              icon={<Shield className="w-5 h-5" />}
              variant="clay"
            />
            <KpiCard
              title="Total Teachers"
              value={adminStats?.total_teachers ?? overview?.total_students ?? 0}
              subtitle="Active professors"
              icon={<GraduationCap className="w-5 h-5" />}
              variant="sand"
            />
            <KpiCard
              title="Enrolled Students"
              value={adminStats?.total_students ?? overview?.total_students ?? 0}
              subtitle="Campus-wide cohort"
              icon={<Users className="w-5 h-5" />}
              variant="clay"
            />
            <KpiCard
              title="Backlog Students"
              value={adminStats?.students_with_backlogs ?? 0}
              subtitle="Failed &ge;1 subject"
              icon={<AlertTriangle className="w-5 h-5" />}
              variant="rose"
            />
          </div>
        </div>
      )}

      {/* HOD VIEW (Section 4 & 7) */}
      {hasRole('hod') && (
        <div className="space-y-8">
          {/* HOD Shortcuts */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Link
              to="/hod/subjects"
              className="p-5 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center justify-between group"
            >
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-xl bg-clay-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 flex items-center justify-center group-hover:bg-clay-500 group-hover:text-white transition-all">
                  <BookOpen className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100">
                    Curriculum Subjects
                  </h3>
                  <p className="text-xs text-ink-500 dark:text-sand-400">
                    Create &amp; assign subjects to faculty
                  </p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link
              to="/faculty"
              className="p-5 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center justify-between group"
            >
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-xl bg-blue-100 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-all">
                  <GraduationCap className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100">
                    Department Faculty
                  </h3>
                  <p className="text-xs text-ink-500 dark:text-sand-400">
                    Add teachers &amp; check mentoring cohorts
                  </p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link
              to="/students"
              className="p-5 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center justify-between group"
            >
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-xl bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center group-hover:bg-emerald-600 group-hover:text-white transition-all">
                  <Users className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100">
                    Department Students
                  </h3>
                  <p className="text-xs text-ink-500 dark:text-sand-400">
                    Review academic marks &amp; backlogs
                  </p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          {/* HOD Stats Grid (Section 4) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
            <KpiCard
              title="Department Faculty"
              value={hodStats?.total_teachers ?? 0}
              subtitle="Teaching professors"
              icon={<GraduationCap className="w-5 h-5" />}
              variant="clay"
            />
            <KpiCard
              title="Enrolled Students"
              value={hodStats?.total_students ?? overview?.total_students ?? 0}
              subtitle={`${user?.department || 'Department'} cohort`}
              icon={<Users className="w-5 h-5" />}
              variant="sand"
            />
            <KpiCard
              title="Curriculum Subjects"
              value={hodStats?.total_subjects ?? 0}
              subtitle="Across all semesters"
              icon={<BookOpen className="w-5 h-5" />}
              variant="clay"
            />
            <KpiCard
              title="Active Backlogs"
              value={hodStats?.students_with_backlogs ?? 0}
              subtitle="Students needing recovery"
              icon={<AlertTriangle className="w-5 h-5" />}
              variant="rose"
            />
          </div>
        </div>
      )}

      {/* TEACHER VIEW (Section 8) */}
      {hasRole('teacher') && (
        <div className="space-y-8">
          {/* Teacher Shortcuts */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Link
              to="/teacher/subjects"
              className="p-5 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center justify-between group"
            >
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-xl bg-clay-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 flex items-center justify-center group-hover:bg-clay-500 group-hover:text-white transition-all">
                  <BookOpen className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100">
                    My Subjects ({teacherSubjects.length})
                  </h3>
                  <p className="text-xs text-ink-500 dark:text-sand-400">
                    Assigned courses allocated by HOD
                  </p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link
              to="/teacher/marks"
              className="p-5 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center justify-between group"
            >
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-xl bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center group-hover:bg-emerald-600 group-hover:text-white transition-all">
                  <ClipboardList className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100">
                    Marks Entry &amp; Gradebook
                  </h3>
                  <p className="text-xs text-ink-500 dark:text-sand-400">
                    Record internal/external &amp; attendance
                  </p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link
              to="/students"
              className="p-5 rounded-2xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 shadow-soft hover:shadow-lift transition-all flex items-center justify-between group"
            >
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-xl bg-blue-100 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-all">
                  <Users className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100">
                    My Mentorship Students
                  </h3>
                  <p className="text-xs text-ink-500 dark:text-sand-400">
                    View student risk &amp; backlogs
                  </p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-ink-400 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          {/* Teacher KPIs */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <KpiCard
              title="Assigned Students"
              value={overview?.total_students || assignedStudents.length}
              subtitle="Direct mentorship cohort"
              icon={<Users className="w-5 h-5" />}
              variant="clay"
            />
            <KpiCard
              title="Assigned High Risk"
              value={overview?.high_risk_count || 0}
              subtitle="Needs mentorship meeting"
              icon={<ShieldAlert className="w-5 h-5" />}
              variant="rose"
            />
            <KpiCard
              title="Pending Counselling"
              value={overview?.pending_counselling_count || 0}
              subtitle="Awaiting session notes"
              icon={<Clock className="w-5 h-5" />}
              variant="amber"
            />
          </div>
        </div>
      )}

      {/* High-Risk Intervention Table (for Admin, HOD, and Teacher) */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden">
        <div className="p-5 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between">
          <div>
            <h3 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
              Priority Intervention Cohort (High Risk Students)
            </h3>
            <p className="text-xs text-ink-500 dark:text-sand-400">
              Students identified by the risk prediction engine requiring immediate faculty mentorship.
            </p>
          </div>
          <Link
            to="/students?level=High"
            className="text-xs font-semibold text-clay-500 hover:text-clay-600 flex items-center"
          >
            View all ({overview?.high_risk_count || highRiskStudents.length}) <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Link>
        </div>

        {loading ? (
          <SkeletonTable rows={4} />
        ) : highRiskStudents.length === 0 ? (
          <div className="p-8 text-center text-xs text-ink-500 dark:text-sand-400">
            No students currently flagged in the High Risk tier.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-50 dark:bg-charcoal-750 text-ink-600 dark:text-sand-400 uppercase font-semibold">
                <tr>
                  <th className="px-5 py-3">Student Name</th>
                  <th className="px-5 py-3">ERP ID</th>
                  <th className="px-5 py-3">Department</th>
                  <th className="px-5 py-3">Semester</th>
                  <th className="px-5 py-3">Risk Tier</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-200 dark:divide-charcoal-700 text-ink-900 dark:text-sand-100">
                {highRiskStudents.map((st) => (
                  <tr
                    key={st.id}
                    className="hover:bg-cream-50/50 dark:hover:bg-charcoal-750/50 transition-colors"
                  >
                    <td className="px-5 py-3.5 font-semibold">
                      <Link to={`/students/${st.id}`} className="hover:text-clay-500">
                        {st.name}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 font-mono text-ink-600 dark:text-sand-300">
                      {st.erp_id}
                    </td>
                    <td className="px-5 py-3.5">{st.department}</td>
                    <td className="px-5 py-3.5">Sem {st.semester}</td>
                    <td className="px-5 py-3.5">
                      <RiskBadge level={st.current_risk?.level || 'High'} isEscalated={true} />
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <Link
                        to={`/students/${st.id}`}
                        className="px-3 py-1.5 rounded-lg bg-cream-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 font-semibold hover:bg-clay-500 hover:text-white transition-all inline-block"
                      >
                        Inspect Profile
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Bulk Import Modal */}
      <ImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onImportComplete={() => {
          loadData();
          setImportModalOpen(false);
        }}
      />
    </div>
  );
};
