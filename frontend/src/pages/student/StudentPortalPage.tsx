import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import {
  studentApi,
  type StudentPerformanceDashboard,
} from '../../api/students';
import { marksApi, type SubjectMarks } from '../../api/marks';
import {
  chatbotApi,
  type ChatMessage,
  type AIChatResponse,
  type StudyPlanResponse,
} from '../../api/chatbot';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { RiskBadge } from '../../components/common/RiskBadge';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  CheckCircle,
  AlertTriangle,
  Shield,
  BookOpen,
  Calendar,
  Bot,
  Send,
  Sparkles,
  RefreshCw,
  Target,
  Clock,
} from 'lucide-react';

export const StudentPortalPage: React.FC = () => {
  const { user } = useAuth();
  const { success, error } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();

  const [dashboard, setDashboard] = useState<StudentPerformanceDashboard | null>(null);
  const [marks, setMarks] = useState<SubjectMarks[]>([]);
  const [studyPlan, setStudyPlan] = useState<StudyPlanResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Derive initial/active tab from URL pathname or ?tab= query parameter
  const resolveActiveTab = useCallback(() => {
    const path = location.pathname.toLowerCase();
    if (path.includes('/marks')) return 'marks';
    if (path.includes('/attendance')) return 'attendance';
    if (path.includes('/backlogs')) return 'backlogs';
    if (path.includes('/risk')) return 'risk';
    if (path.includes('/counselling')) return 'chat';
    if (path.includes('/study-plan')) return 'study_plan';
    return searchParams.get('tab') || 'performance';
  }, [location.pathname, searchParams]);

  const [activeTab, setActiveTab] = useState<string>(resolveActiveTab);

  useEffect(() => {
    setActiveTab(resolveActiveTab());
  }, [resolveActiveTab]);

  // Sync tab with URL
  const handleTabChange = (tabKey: string) => {
    setActiveTab(tabKey);
    setSearchParams({ tab: tabKey });
  };

  // Chatbot State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: `Hello ${user?.first_name || 'Student'}! I am your AI Academic Counsellor. I have real-time access to your academic marks, backlogs, attendance, and risk assessment. How can I help you improve your grades or plan your studies today?`,
    },
  ]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [suggestedActions, setSuggestedActions] = useState<string[]>([
    'How do I clear my active backlogs?',
    'Create a daily schedule for my weak subjects',
    'How can I improve my attendance above 75%?',
    'What should I focus on for my upcoming semester exams?',
  ]);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Plan regeneration state
  const [generatingPlan, setGeneratingPlan] = useState<boolean>(false);

  const errorRef = useRef(error);
  useEffect(() => {
    errorRef.current = error;
  }, [error]);

  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    try {
      // 1. Fetch comprehensive performance dashboard
      const dash = await studentApi.getMyPerformanceDashboard();
      setDashboard(dash);

      // 2. Fetch detailed marks and study plan in parallel
      const [marksList, plan] = await Promise.all([
        marksApi.getStudentMarks(dash.student_id).catch(() => []),
        chatbotApi.getStudyPlan(dash.student_id).catch(() => null),
      ]);
      setMarks(marksList);
      setStudyPlan(plan);

      // Dynamic chat suggestions tailored to the student's actual backlogs
      if (dash.active_backlogs > 0) {
        const backlogNames = dash.backlogs_list.map((b) => b.subject_name).join(', ');
        setSuggestedActions([
          `How can I prioritize clearing backlogs in ${backlogNames}?`,
          'Give me a 2-hour daily study routine for my lowest scoring subject',
          'How does my attendance impact my overall dropout risk?',
          'What study materials should I use for backlog preparation?',
        ]);
      }
    } catch (err: any) {
      console.error(err);
      errorRef.current('Failed to Load Dashboard', err.message || 'Could not fetch your performance data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  useEffect(() => {
    if (activeTab === 'chat') {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, activeTab]);

  const handleSendMessage = async (customText?: string) => {
    const textToSend = customText || inputMessage;
    if (!textToSend.trim() || chatLoading) return;

    const userMsg: ChatMessage = { role: 'user', content: textToSend };
    setChatMessages((prev) => [...prev, userMsg]);
    if (!customText) setInputMessage('');
    setChatLoading(true);

    try {
      const res: AIChatResponse = await chatbotApi.chatWithCounsellor({
        student_id: dashboard?.student_id,
        message: textToSend,
        conversation_history: [...chatMessages, userMsg],
      });

      setChatMessages((prev) => [...prev, { role: 'assistant', content: res.reply }]);

      if (res.suggested_actions && res.suggested_actions.length > 0) {
        setSuggestedActions(res.suggested_actions);
      }
    } catch {
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content:
            'I am currently experiencing a connection delay with the counselling engine. Please review your performance metrics and study schedule while I reconnect.',
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleRegeneratePlan = async () => {
    if (!dashboard) return;
    setGeneratingPlan(true);
    try {
      const newPlan = await chatbotApi.generateStudyPlan(dashboard.student_id);
      setStudyPlan(newPlan);
      success('Study Plan Refreshed', 'Personalized 7-day schedule and backlog improvement plans updated.');
    } catch (err: any) {
      error('Generation Failed', err.message || 'Could not regenerate study plan.');
    } finally {
      setGeneratingPlan(false);
    }
  };

  if (loading && !dashboard) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 text-center text-xs text-ink-500 dark:text-sand-400">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-clay-500 mb-2" />
        Loading your personal academic performance dashboard...
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fade-up">
      {/* 1. Header Profile Banner */}
      <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 p-6 sm:p-8 shadow-soft">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-sand-200 dark:border-charcoal-700">
          <div className="flex items-start space-x-4">
            <div className="w-16 h-16 rounded-2xl bg-clay-500 text-white font-bold text-2xl flex items-center justify-center shadow-soft shrink-0">
              {dashboard?.student_name?.[0]?.toUpperCase() || user?.first_name?.[0]?.toUpperCase() || 'S'}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100">
                  {dashboard?.student_name || `${user?.first_name} ${user?.last_name}`}
                </h1>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400 font-semibold uppercase">
                  Active Student
                </span>
              </div>
              <p className="text-xs text-ink-500 dark:text-sand-400 mt-1">
                PRN: <strong className="font-mono text-ink-800 dark:text-sand-200">{dashboard?.erp_id}</strong> &bull; {dashboard?.department} &bull; Semester {dashboard?.semester} &bull; Batch {dashboard?.batch}
              </p>
              <p className="text-xs text-ink-400 dark:text-sand-500 mt-0.5">
                Degree: {dashboard?.course || 'B.Tech Engineering'} &bull; Campus ID: {dashboard?.student_id.slice(-6)}
              </p>
            </div>
          </div>

          {/* Risk Level Badge */}
          <div className="flex flex-col items-start md:items-end">
            <span className="text-[11px] font-semibold text-ink-400 dark:text-sand-500 uppercase tracking-wider mb-1">
              Dropout Risk Level
            </span>
            <RiskBadge level={dashboard?.current_risk_level || 'Low'} size="lg" />
            {dashboard?.risk_score !== null && dashboard?.risk_score !== undefined && (
              <span className="text-xs font-semibold text-ink-600 dark:text-sand-300 mt-1">
                Risk Score: <strong>{Math.round(dashboard.risk_score)} / 100</strong>
              </span>
            )}
          </div>
        </div>

        {/* 2. Quick Performance Summary Row (Section 3) */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 pt-6 text-center">
          <div className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700">
            <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 block">Average Marks</span>
            <p className="font-display text-xl font-bold text-ink-900 dark:text-sand-100 mt-1">
              {dashboard?.average_marks}%
            </p>
            <span className="text-[10px] text-ink-400 dark:text-sand-500">Current Semester</span>
          </div>

          <div className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700">
            <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 block">CGPA</span>
            <p className="font-display text-xl font-bold text-clay-600 dark:text-clay-400 mt-1">
              {dashboard?.cgpa}
            </p>
            <span className="text-[10px] text-ink-400 dark:text-sand-500">Scale of 10.0</span>
          </div>

          <div className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700">
            <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 block">Attendance</span>
            <p className={`font-display text-xl font-bold mt-1 ${
              (dashboard?.overall_attendance || 100) < 75 ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'
            }`}>
              {dashboard?.overall_attendance}%
            </p>
            <span className="text-[10px] text-ink-400 dark:text-sand-500">
              {(dashboard?.overall_attendance || 100) < 75 ? 'Below 75% req.' : 'Satisfactory'}
            </span>
          </div>

          <div className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700">
            <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 block">Subjects</span>
            <p className="font-display text-xl font-bold text-ink-900 dark:text-sand-100 mt-1">
              {dashboard?.total_subjects}
            </p>
            <span className="text-[10px] text-ink-400 dark:text-sand-500">Registered</span>
          </div>

          <div className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700">
            <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 block">Passed</span>
            <p className="font-display text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
              {dashboard?.passed_subjects}
            </p>
            <span className="text-[10px] text-ink-400 dark:text-sand-500">Cleared</span>
          </div>

          <div className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700">
            <span className="text-[11px] font-semibold text-rose-600 dark:text-rose-400 block">Backlogs</span>
            <p className="font-display text-xl font-bold text-rose-600 dark:text-rose-400 mt-1">
              {dashboard?.active_backlogs}
            </p>
            <span className="text-[10px] text-rose-500 dark:text-rose-400/80">Active</span>
          </div>

          <div className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700">
            <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 block">Trend</span>
            <div className="flex items-center justify-center space-x-1 mt-1 font-display font-bold text-base text-ink-900 dark:text-sand-100">
              {dashboard?.trend_direction === 'Improving' ? (
                <>
                  <TrendingUp className="w-4 h-4 text-emerald-500" />
                  <span className="text-emerald-600 text-sm">Improving</span>
                </>
              ) : dashboard?.trend_direction === 'Declining' ? (
                <>
                  <TrendingDown className="w-4 h-4 text-rose-500" />
                  <span className="text-rose-600 text-sm">Declining</span>
                </>
              ) : (
                <>
                  <Minus className="w-4 h-4 text-amber-500" />
                  <span className="text-amber-600 text-sm">Stable</span>
                </>
              )}
            </div>
            <span className="text-[10px] text-ink-400 dark:text-sand-500">vs Previous Sem</span>
          </div>
        </div>
      </div>

      {/* Attendance Warnings Banner (Section 6) */}
      {dashboard?.attendance_warnings && dashboard.attendance_warnings.length > 0 && (
        <div className="p-4 rounded-2xl bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-800/50 flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-display font-bold text-xs text-amber-900 dark:text-amber-200 uppercase tracking-wider">
              &bull; Academic Attendance Warning
            </h4>
            {dashboard.attendance_warnings.map((warn, i) => (
              <p key={i} className="text-xs text-amber-800 dark:text-amber-300/90 leading-relaxed">
                {warn}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-sand-200 dark:border-charcoal-700 overflow-x-auto space-x-2 sm:space-x-4 text-xs sm:text-sm font-semibold">
        <button
          onClick={() => handleTabChange('performance')}
          className={`pb-3 px-2 transition-all flex items-center shrink-0 ${
            activeTab === 'performance'
              ? 'border-b-2 border-clay-500 text-clay-600 dark:text-clay-400'
              : 'text-ink-500 dark:text-sand-400 hover:text-ink-800'
          }`}
        >
          <BarChart3 className="w-4 h-4 mr-1.5" />
          My Performance
        </button>

        <button
          onClick={() => handleTabChange('marks')}
          className={`pb-3 px-2 transition-all flex items-center shrink-0 ${
            activeTab === 'marks'
              ? 'border-b-2 border-clay-500 text-clay-600 dark:text-clay-400'
              : 'text-ink-500 dark:text-sand-400 hover:text-ink-800'
          }`}
        >
          <BookOpen className="w-4 h-4 mr-1.5" />
          My Marks ({dashboard?.subjects?.length || 0})
        </button>

        <button
          onClick={() => handleTabChange('attendance')}
          className={`pb-3 px-2 transition-all flex items-center shrink-0 ${
            activeTab === 'attendance'
              ? 'border-b-2 border-clay-500 text-clay-600 dark:text-clay-400'
              : 'text-ink-500 dark:text-sand-400 hover:text-ink-800'
          }`}
        >
          <Clock className="w-4 h-4 mr-1.5" />
          My Attendance
        </button>

        <button
          onClick={() => handleTabChange('backlogs')}
          className={`pb-3 px-2 transition-all flex items-center shrink-0 ${
            activeTab === 'backlogs'
              ? 'border-b-2 border-clay-500 text-clay-600 dark:text-clay-400'
              : 'text-ink-500 dark:text-sand-400 hover:text-ink-800'
          }`}
        >
          <AlertTriangle className="w-4 h-4 mr-1.5" />
          My Backlogs ({dashboard?.active_backlogs || 0})
        </button>

        <button
          onClick={() => handleTabChange('risk')}
          className={`pb-3 px-2 transition-all flex items-center shrink-0 ${
            activeTab === 'risk'
              ? 'border-b-2 border-clay-500 text-clay-600 dark:text-clay-400'
              : 'text-ink-500 dark:text-sand-400 hover:text-ink-800'
          }`}
        >
          <Shield className="w-4 h-4 mr-1.5" />
          My Dropout Risk
        </button>

        <button
          onClick={() => handleTabChange('chat')}
          className={`pb-3 px-2 transition-all flex items-center shrink-0 ${
            activeTab === 'chat'
              ? 'border-b-2 border-clay-500 text-clay-600 dark:text-clay-400'
              : 'text-ink-500 dark:text-sand-400 hover:text-ink-800'
          }`}
        >
          <Bot className="w-4 h-4 mr-1.5" />
          AI Counselling
        </button>

        <button
          onClick={() => handleTabChange('study_plan')}
          className={`pb-3 px-2 transition-all flex items-center shrink-0 ${
            activeTab === 'study_plan'
              ? 'border-b-2 border-clay-500 text-clay-600 dark:text-clay-400'
              : 'text-ink-500 dark:text-sand-400 hover:text-ink-800'
          }`}
        >
          <Calendar className="w-4 h-4 mr-1.5" />
          My Study Plan
        </button>
      </div>

      {/* =========================================================================
          TAB 1: MY PERFORMANCE (Sections 3, 4, 5, 8, 9)
         ========================================================================= */}
      {activeTab === 'performance' && (
        <div className="space-y-6">
          {/* Section 4: Subject-wise Performance Overview */}
          <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden">
            <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between">
              <div>
                <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 flex items-center">
                  <BarChart3 className="w-5 h-5 mr-2 text-clay-500" />
                  Subject-Wise Academic Performance
                </h3>
                <p className="text-xs text-ink-500 dark:text-sand-400">
                  Continuous evaluation marks, grades, and academic classification
                </p>
              </div>
              <span className="text-xs text-ink-500 dark:text-sand-400">
                Semester {dashboard?.semester}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-cream-50 dark:bg-charcoal-850 text-ink-500 dark:text-sand-400 border-b border-sand-200 dark:border-charcoal-700">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Subject</th>
                    <th className="px-4 py-3 font-semibold text-center">Marks</th>
                    <th className="px-4 py-3 font-semibold text-center">Grade</th>
                    <th className="px-4 py-3 font-semibold text-center">Attendance</th>
                    <th className="px-4 py-3 font-semibold text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-sand-200 dark:divide-charcoal-750 text-ink-900 dark:text-sand-100">
                  {dashboard?.subjects?.map((sub) => (
                    <tr key={sub.subject_id} className="hover:bg-sand-50/50 dark:hover:bg-charcoal-750/50">
                      <td className="px-5 py-3.5">
                        <div className="font-semibold text-sm">{sub.subject_name}</div>
                        <div className="text-[10px] text-ink-400 font-mono">
                          {sub.subject_code} &bull; Sem {sub.semester}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-center font-bold text-sm">
                        {sub.marks}/100
                      </td>
                      <td className="px-4 py-3.5 text-center">
                        <span
                          className={`inline-block w-7 py-0.5 text-center rounded text-xs font-bold ${
                            sub.grade === 'F'
                              ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
                              : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400'
                          }`}
                        >
                          {sub.grade}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-center">
                        <span className={`font-semibold ${sub.attendance < 75 ? 'text-rose-600 dark:text-rose-400' : ''}`}>
                          {sub.attendance}%
                        </span>
                        {sub.attendance_warning && (
                          <span className="block text-[9px] text-rose-500">Low Attendance</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-center">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            sub.status === 'Backlog'
                              ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-400'
                              : sub.status === 'Weak'
                              ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-400'
                              : sub.status === 'Strong'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400'
                              : 'bg-sand-200 text-ink-700 dark:bg-charcoal-700 dark:text-sand-300'
                          }`}
                        >
                          {sub.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 5 & 9: Trend and Improvement Recommendations Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Section 5: Historical Performance Trend */}
            <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-sand-200 dark:border-charcoal-700">
                <h3 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100 flex items-center">
                  <TrendingUp className="w-4 h-4 mr-2 text-clay-500" />
                  Performance Trajectory Across Semesters
                </h3>
                <span
                  className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                    dashboard?.trend_direction === 'Improving'
                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400'
                      : dashboard?.trend_direction === 'Declining'
                      ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-400'
                      : 'bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-400'
                  }`}
                >
                  {dashboard?.trend_direction}
                </span>
              </div>

              {dashboard?.historical_trend && dashboard.historical_trend.length > 0 ? (
                <div className="space-y-3">
                  {dashboard.historical_trend.map((tr) => (
                    <div
                      key={tr.semester}
                      className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700 flex items-center justify-between text-xs"
                    >
                      <div>
                        <span className="font-bold text-ink-900 dark:text-sand-100">
                          Semester {tr.semester}
                        </span>
                        <span className="text-[10px] text-ink-400 block">AY {tr.academic_year}</span>
                      </div>
                      <div className="flex items-center space-x-6 text-right">
                        <div>
                          <span className="text-[10px] text-ink-400 block">Marks</span>
                          <span className="font-bold text-ink-900 dark:text-sand-100">{tr.marks}%</span>
                        </div>
                        <div>
                          <span className="text-[10px] text-ink-400 block">Attendance</span>
                          <span className="font-bold text-ink-900 dark:text-sand-100">{tr.attendance}%</span>
                        </div>
                        <div>
                          <span className="text-[10px] text-ink-400 block">Backlogs</span>
                          <span className={`font-bold ${tr.backlogs > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                            {tr.backlogs}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-ink-500 dark:text-sand-400">
                  Initial semester records active. Performance trends will track as additional terms complete.
                </p>
              )}
            </div>

            {/* Section 9: How to Improve Recommendations */}
            <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-sand-200 dark:border-charcoal-700">
                <h3 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100 flex items-center">
                  <Target className="w-4 h-4 mr-2 text-clay-500" />
                  Personalized Improvement Action Plan
                </h3>
                <span className="text-[10px] text-ink-400">Data-driven</span>
              </div>

              <div className="space-y-2">
                {dashboard?.recommendations?.map((rec, rIdx) => (
                  <div
                    key={rIdx}
                    className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700 text-xs text-ink-700 dark:text-sand-200 flex items-start space-x-2"
                  >
                    <span className="w-5 h-5 rounded-full bg-clay-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 font-bold flex items-center justify-center shrink-0 text-[10px]">
                      {rIdx + 1}
                    </span>
                    <span className="leading-relaxed">{rec}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2: MY MARKS (Detailed Grade Sheet)
         ========================================================================= */}
      {activeTab === 'marks' && (
        <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden">
          <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between">
            <div>
              <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100">
                Detailed Academic Continuous Evaluation
              </h3>
              <p className="text-xs text-ink-500 dark:text-sand-400">
                Internal, external, practical, assignment breakdown
              </p>
            </div>
            <button
              onClick={fetchDashboardData}
              className="inline-flex items-center text-xs font-semibold text-clay-600 dark:text-clay-400 hover:underline"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1" />
              Refresh
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-50 dark:bg-charcoal-850 text-ink-500 dark:text-sand-400 border-b border-sand-200 dark:border-charcoal-700">
                <tr>
                  <th className="px-5 py-3 font-semibold">Subject & Code</th>
                  <th className="px-4 py-3 font-semibold text-center">Internal (/50)</th>
                  <th className="px-4 py-3 font-semibold text-center">External (/100)</th>
                  <th className="px-4 py-3 font-semibold text-center">Practical (/50)</th>
                  <th className="px-4 py-3 font-semibold text-center">Assignment (/50)</th>
                  <th className="px-4 py-3 font-semibold text-center">Total (/100)</th>
                  <th className="px-4 py-3 font-semibold text-center">Grade</th>
                  <th className="px-4 py-3 font-semibold text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-200 dark:divide-charcoal-750 text-ink-900 dark:text-sand-100">
                {marks.map((m) => (
                  <tr key={m.id} className="hover:bg-sand-50/50 dark:hover:bg-charcoal-750/50">
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-sm">{m.subject_name}</div>
                      <div className="text-[10px] text-ink-400 font-mono">
                        {m.subject_code} &bull; Sem {m.semester}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-center">{m.internal_marks ?? '-'}</td>
                    <td className="px-4 py-3.5 text-center">{m.external_marks ?? '-'}</td>
                    <td className="px-4 py-3.5 text-center">{m.practical_marks ?? '-'}</td>
                    <td className="px-4 py-3.5 text-center">{m.assignment_marks ?? '-'}</td>
                    <td className="px-4 py-3.5 text-center font-bold text-sm">{m.total_marks}/100</td>
                    <td className="px-4 py-3.5 text-center">
                      <span
                        className={`inline-block w-6 py-0.5 rounded text-xs font-bold ${
                          m.grade === 'F'
                            ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
                            : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400'
                        }`}
                      >
                        {m.grade}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-center">
                      {m.is_backlog ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-400">
                          Backlog
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400">
                          Pass
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 3: MY ATTENDANCE (Section 6)
         ========================================================================= */}
      {activeTab === 'attendance' && (
        <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-sand-200 dark:border-charcoal-700">
            <div>
              <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 flex items-center">
                <Clock className="w-5 h-5 mr-2 text-clay-500" />
                Personal Attendance Tracking
              </h3>
              <p className="text-xs text-ink-500 dark:text-sand-400">
                Minimum 75% attendance is required per subject under university regulations.
              </p>
            </div>
            <div className="p-3 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200 dark:border-charcoal-700 text-center">
              <span className="text-[10px] text-ink-400 font-bold uppercase">Overall Attendance</span>
              <p
                className={`font-display text-2xl font-bold ${
                  (dashboard?.overall_attendance || 100) < 75
                    ? 'text-rose-600 dark:text-rose-400'
                    : 'text-emerald-600 dark:text-emerald-400'
                }`}
              >
                {dashboard?.overall_attendance}%
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {dashboard?.subjects?.map((sub) => (
              <div
                key={sub.subject_id}
                className="p-4 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-bold text-xs text-ink-900 dark:text-sand-100">
                      {sub.subject_name}
                    </span>
                    <span className="text-[10px] text-ink-400 block font-mono">{sub.subject_code}</span>
                  </div>
                  <span
                    className={`font-display font-bold text-sm ${
                      sub.attendance < 75 ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'
                    }`}
                  >
                    {sub.attendance}%
                  </span>
                </div>

                <div className="w-full bg-sand-200 dark:bg-charcoal-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      sub.attendance < 75 ? 'bg-rose-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.min(100, sub.attendance)}%` }}
                  />
                </div>

                {sub.attendance < 75 && (
                  <p className="text-[11px] text-rose-600 dark:text-rose-400 flex items-center pt-1">
                    <AlertTriangle className="w-3 h-3 mr-1" />
                    Warning: Attendance is below 75%. Attend upcoming lectures to prevent exam debarment.
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 4: MY BACKLOGS (Section 7)
         ========================================================================= */}
      {activeTab === 'backlogs' && (
        <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-sand-200 dark:border-charcoal-700">
            <div>
              <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 flex items-center">
                <AlertTriangle className="w-5 h-5 mr-2 text-rose-500" />
                Active Backlog Clearance Hub
              </h3>
              <p className="text-xs text-ink-500 dark:text-sand-400">
                Failed subjects (Total marks &lt; 40 or Grade &apos;F&apos;) requiring clearance
              </p>
            </div>
            <span className="text-xs px-3 py-1 rounded-full font-bold bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-400">
              {dashboard?.active_backlogs || 0} Backlogs Active
            </span>
          </div>

          {!dashboard?.backlogs_list || dashboard.backlogs_list.length === 0 ? (
            <div className="p-12 text-center space-y-2">
              <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto" />
              <h4 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100">
                No Active Backlogs!
              </h4>
              <p className="text-xs text-ink-500 dark:text-sand-400 max-w-sm mx-auto">
                Congratulations! You have passed all your registered curriculum subjects. Keep up the consistent effort.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {dashboard.backlogs_list.map((bk, bIdx) => (
                <div
                  key={bIdx}
                  className="p-5 rounded-2xl bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/50 space-y-3"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-400">
                        {bk.status}
                      </span>
                      <h4 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 mt-2">
                        {bk.subject_name}
                      </h4>
                      <span className="text-xs text-ink-400 font-mono">{bk.subject_code}</span>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-rose-600 text-white">
                        Priority: {bk.priority}
                      </span>
                      <span className="font-display font-bold text-lg text-rose-600 block mt-1">
                        {bk.previous_marks}/100
                      </span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-white dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 text-xs">
                    <strong className="text-ink-800 dark:text-sand-200 block mb-0.5">
                      Clearance Advice:
                    </strong>
                    <p className="text-ink-600 dark:text-sand-300 leading-relaxed">
                      {bk.action_advice}
                    </p>
                  </div>

                  <button
                    onClick={() => handleTabChange('chat')}
                    className="w-full inline-flex items-center justify-center px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-soft transition-all"
                  >
                    <Bot className="w-3.5 h-3.5 mr-1.5" />
                    Ask AI Counsellor for {bk.subject_name} Study Plan
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          TAB 5: MY DROPOUT RISK (Section 8)
         ========================================================================= */}
      {activeTab === 'risk' && (
        <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-sand-200 dark:border-charcoal-700">
            <div>
              <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 flex items-center">
                <Shield className="w-5 h-5 mr-2 text-clay-500" />
                Dropout Risk Analysis &amp; Genuine Contributing Factors
              </h3>
              <p className="text-xs text-ink-500 dark:text-sand-400">
                Transparent evaluation computed from marks, attendance, and semester backlogs
              </p>
            </div>
            <RiskBadge level={dashboard?.current_risk_level || 'Low'} size="md" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {dashboard?.risk_factors?.map((f, fIdx) => (
              <div
                key={fIdx}
                className="p-4 rounded-2xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200 dark:border-charcoal-700 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-ink-900 dark:text-sand-100">
                    {f.name}
                  </span>
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                      f.risk >= 0.6
                        ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-400'
                        : f.risk >= 0.3
                        ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-400'
                        : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400'
                    }`}
                  >
                    Risk Contribution: {Math.round(f.risk * 100)}%
                  </span>
                </div>

                <p className="text-xs text-ink-600 dark:text-sand-300 leading-relaxed">
                  {f.explanation}
                </p>

                <div className="w-full bg-sand-200 dark:bg-charcoal-700 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full ${
                      f.risk >= 0.6 ? 'bg-rose-500' : f.risk >= 0.3 ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.round(f.risk * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 6: AI COUNSELLING (Section 10)
         ========================================================================= */}
      {activeTab === 'chat' && (
        <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden flex flex-col h-[650px]">
          <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 bg-cream-50 dark:bg-charcoal-850 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-clay-500 text-white flex items-center justify-center shadow-soft">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100 flex items-center">
                  AI Academic Counsellor
                  <span className="ml-2 px-2 py-0.5 rounded-full text-[10px] bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400 font-bold">
                    Context: {dashboard?.student_name} (CGPA: {dashboard?.cgpa})
                  </span>
                </h3>
                <p className="text-[11px] text-ink-500 dark:text-sand-400">
                  Section 10: Guidance formulated with your live marks, {dashboard?.active_backlogs || 0} backlogs, and {dashboard?.overall_attendance}% attendance.
                </p>
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 p-6 overflow-y-auto space-y-4">
            {chatMessages.map((msg, i) => {
              const isUser = msg.role === 'user';
              return (
                <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] sm:max-w-[70%] p-4 rounded-2xl text-xs leading-relaxed ${
                      isUser
                        ? 'bg-clay-500 text-white rounded-br-none shadow-soft'
                        : 'bg-cream-50 dark:bg-charcoal-850 border border-sand-200 dark:border-charcoal-700 text-ink-900 dark:text-sand-100 rounded-bl-none shadow-sm whitespace-pre-line'
                    }`}
                  >
                    {!isUser && (
                      <div className="flex items-center space-x-1.5 text-[10px] font-bold text-clay-600 dark:text-clay-400 mb-1">
                        <Sparkles className="w-3 h-3" />
                        <span>AI Counsellor</span>
                      </div>
                    )}
                    {msg.content}
                  </div>
                </div>
              );
            })}

            {chatLoading && (
              <div className="flex justify-start">
                <div className="p-4 rounded-2xl rounded-bl-none bg-cream-50 dark:bg-charcoal-850 border border-sand-200 dark:border-charcoal-700 text-xs text-ink-500 dark:text-sand-400 flex items-center space-x-2">
                  <Bot className="w-4 h-4 animate-spin text-clay-500" />
                  <span>Evaluating your academic profile &amp; formulating advice...</span>
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Quick Prompts */}
          <div className="px-6 py-2 bg-cream-50/50 dark:bg-charcoal-850/50 border-t border-sand-200 dark:border-charcoal-700 overflow-x-auto flex space-x-2">
            {suggestedActions.map((act, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(act)}
                disabled={chatLoading}
                className="whitespace-nowrap px-3 py-1 rounded-full bg-white dark:bg-charcoal-800 border border-sand-300 dark:border-charcoal-700 text-[11px] font-semibold text-ink-700 dark:text-sand-300 hover:border-clay-500 hover:text-clay-600 transition-colors shrink-0"
              >
                {act}
              </button>
            ))}
          </div>

          {/* Chat Input */}
          <div className="p-4 border-t border-sand-200 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 flex items-center space-x-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Ask about clearing your backlogs, improving marks, or daily study routines..."
              disabled={chatLoading}
              className="flex-1 px-4 py-2.5 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={chatLoading || !inputMessage.trim()}
              className="p-2.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white disabled:opacity-40 shadow-soft transition-all"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 7: MY STUDY PLAN (7-Day Schedule & Backlog Strategies)
         ========================================================================= */}
      {activeTab === 'study_plan' && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="font-display font-bold text-lg text-ink-900 dark:text-sand-100 flex items-center">
                <Calendar className="w-5 h-5 mr-2 text-clay-500" />
                Personalized 7-Day Study Schedule
              </h3>
              <p className="text-xs text-ink-500 dark:text-sand-400 mt-1">
                Optimized around your weak subjects and backlog recovery targets.
              </p>
            </div>
            <button
              onClick={handleRegeneratePlan}
              disabled={generatingPlan}
              className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift disabled:opacity-50 transition-all shrink-0"
            >
              <Sparkles className={`w-3.5 h-3.5 mr-1.5 ${generatingPlan ? 'animate-spin' : ''}`} />
              {generatingPlan ? 'Regenerating...' : 'Regenerate Study Plan'}
            </button>
          </div>

          {studyPlan?.weekly_schedule && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(studyPlan.weekly_schedule).map(([day, slots]) => (
                <div
                  key={day}
                  className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-5 shadow-soft space-y-3"
                >
                  <div className="flex items-center justify-between pb-2 border-b border-sand-200 dark:border-charcoal-750">
                    <h4 className="font-display font-bold text-sm text-ink-900 dark:text-sand-100 capitalize">
                      {day}
                    </h4>
                    <span className="text-[10px] font-semibold text-clay-600 dark:text-clay-400 bg-clay-50 dark:bg-charcoal-700 px-2 py-0.5 rounded-md">
                      {slots.reduce((acc, s) => acc + s.hours, 0)} hrs total
                    </span>
                  </div>

                  <div className="space-y-2">
                    {slots.map((slot, sIdx) => (
                      <div
                        key={sIdx}
                        className="p-3 rounded-xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-ink-900 dark:text-sand-100">
                            {slot.subject}
                          </span>
                          <span className="font-mono text-[10px] text-ink-500 dark:text-sand-400">
                            {slot.hours} hrs
                          </span>
                        </div>
                        <p className="text-[11px] text-ink-500 dark:text-sand-400">
                          {slot.activity}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
