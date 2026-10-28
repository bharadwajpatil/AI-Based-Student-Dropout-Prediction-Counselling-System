import React, { useState, useEffect, useCallback } from 'react';
import { analyticsApi } from '../../api/analytics';
import type {
  AnalyticsOverview,
  DistributionItem,
  CorrelationData,
} from '../../types';
import { KpiCard } from '../../components/common/KpiCard';
import { SkeletonCard } from '../../components/common/Skeleton';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  Cell,
  CartesianGrid,
} from 'recharts';
import {
  BarChart3,
  Download,
  Users,
  ShieldAlert,
  Percent,
  Award,
} from 'lucide-react';

export const AnalyticsPage: React.FC = () => {
  const { hasRole } = useAuth();
  const { success, error } = useToast();

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [distribution, setDistribution] = useState<DistributionItem[]>([]);
  const [attendanceCorr, setAttendanceCorr] = useState<CorrelationData | null>(null);
  const [marksCorr, setMarksCorr] = useState<CorrelationData | null>(null);
  const [departmentData, setDepartmentData] = useState<{ department: string; total_students: number; high_risk_count: number }[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [exporting, setExporting] = useState<boolean>(false);
  const [selectedDept, setSelectedDept] = useState<string>('');

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, dist, att, mrk, depts] = await Promise.all([
        analyticsApi.getOverview(selectedDept || undefined),
        analyticsApi.getDistribution(selectedDept || undefined),
        analyticsApi.getAttendanceVsRisk(selectedDept || undefined),
        analyticsApi.getMarksVsRisk(selectedDept || undefined),
        analyticsApi.getByDepartment(),
      ]);

      setOverview(ov);
      setDistribution(dist.distribution || []);
      setAttendanceCorr(att);
      setMarksCorr(mrk);
      setDepartmentData(depts.departments || []);
    } catch (err) {
      console.error('Failed to load analytics', err);
    } finally {
      setLoading(false);
    }
  }, [selectedDept]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const blob = await analyticsApi.downloadHighRiskCsv(selectedDept || undefined);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `high_risk_students_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      success('Export Ready', 'High-risk student roster downloaded securely.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      error('Export Error', msg);
    } finally {
      setExporting(false);
    }
  };

  const getTierColor = (level: string) => {
    switch (level) {
      case 'High':
        return '#E5787A'; // rose-400
      case 'Medium':
        return '#F2B84B'; // amber-400
      case 'Low':
        return '#5E8C6E'; // sage-600
      default:
        return '#CBB291'; // sand-400
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-up">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-sand-200 dark:border-charcoal-800">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100 flex items-center">
            <BarChart3 className="w-7 h-7 mr-2.5 text-clay-500" />
            Institutional Analytics & Risk Trends
          </h1>
          <p className="text-xs sm:text-sm text-ink-500 dark:text-sand-400 mt-1">
            Correlations, cohort distribution, and automated export reports.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {hasRole('admin') && (
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs font-medium text-ink-900 dark:text-sand-100"
            >
              <option value="">All Departments</option>
              <option value="Computer Science">Computer Science</option>
              <option value="Electronics">Electronics</option>
              <option value="Mechanical">Mechanical</option>
              <option value="Civil">Civil</option>
            </select>
          )}

          <button
            onClick={handleExportCsv}
            disabled={exporting}
            className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift disabled:opacity-60 transition-all"
          >
            <Download className="w-4 h-4 mr-1.5" />
            {exporting ? 'Exporting...' : 'Export High-Risk CSV'}
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <KpiCard
            title="Enrolled Cohort"
            value={overview?.total_students || 0}
            subtitle="Active student pool"
            icon={<Users className="w-5 h-5" />}
            variant="clay"
          />
          <KpiCard
            title="Average Attendance"
            value={Math.round(overview?.average_attendance || 0)}
            subtitle="Campus benchmark"
            icon={<Percent className="w-5 h-5" />}
            variant="sage"
            suffix="%"
          />
          <KpiCard
            title="Average Marks"
            value={Math.round(overview?.average_marks || 0)}
            subtitle="Academic aggregate"
            icon={<Award className="w-5 h-5" />}
            variant="amber"
            suffix="%"
          />
          <KpiCard
            title="High Risk Ratio"
            value={
              overview && overview.total_students > 0
                ? Math.round((overview.high_risk_count / overview.total_students) * 100)
                : 0
            }
            subtitle="Of total student population"
            icon={<ShieldAlert className="w-5 h-5" />}
            variant="rose"
            suffix="%"
          />
        </div>
      )}

      {/* Risk Distribution Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-4">
          <div>
            <h3 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
              Risk Tier Population Distribution
            </h3>
            <p className="text-xs text-ink-500 dark:text-sand-400">
              Breakdown across active students categorized by the deterministic risk model.
            </p>
          </div>

          <div className="h-64 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distribution}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EADBC8" opacity={0.5} />
                <XAxis dataKey="level" tick={{ fontSize: 11, fill: '#4A3B32' }} />
                <YAxis tick={{ fontSize: 11, fill: '#4A3B32' }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFBF5',
                    borderRadius: '12px',
                    borderColor: '#EADBC8',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                  {distribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={getTierColor(entry.level)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Department Comparison Chart */}
        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-4">
          <div>
            <h3 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
              Departmental Risk Distribution
            </h3>
            <p className="text-xs text-ink-500 dark:text-sand-400">
              High-risk students vs total enrollment across academic departments.
            </p>
          </div>

          <div className="h-64 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={departmentData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EADBC8" opacity={0.5} />
                <XAxis dataKey="department" tick={{ fontSize: 11, fill: '#4A3B32' }} />
                <YAxis tick={{ fontSize: 11, fill: '#4A3B32' }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFBF5',
                    borderRadius: '12px',
                    borderColor: '#EADBC8',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="total_students" name="Total Students" fill="#D2734E" radius={[6, 6, 0, 0]} />
                <Bar dataKey="high_risk_count" name="High Risk" fill="#E5787A" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Scatter Correlations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Attendance vs Risk */}
        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
                Attendance vs. Risk Score
              </h3>
              <p className="text-xs text-ink-500 dark:text-sand-400">
                Inversely correlated: lower attendance leads to heightened dropout likelihood.
              </p>
            </div>
            {attendanceCorr && (
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-cream-100 dark:bg-charcoal-750 text-clay-600 dark:text-clay-400 border border-sand-200 dark:border-charcoal-700">
                Pearson r: {attendanceCorr.correlation_r?.toFixed(2) || '0.00'}
              </span>
            )}
          </div>

          <div className="h-64 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EADBC8" opacity={0.5} />
                <XAxis
                  type="number"
                  dataKey="x"
                  name="Attendance"
                  unit="%"
                  domain={[0, 100]}
                  tick={{ fontSize: 11, fill: '#4A3B32' }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name="Risk Score"
                  unit="%"
                  domain={[0, 100]}
                  tick={{ fontSize: 11, fill: '#4A3B32' }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  contentStyle={{
                    backgroundColor: '#FFFBF5',
                    borderRadius: '12px',
                    borderColor: '#EADBC8',
                    fontSize: '12px',
                  }}
                />
                <Scatter name="Students" data={attendanceCorr?.data_points || []} fill="#D2734E" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Marks vs Risk */}
        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
                Marks Aggregate vs. Risk Score
              </h3>
              <p className="text-xs text-ink-500 dark:text-sand-400">
                Academic achievement correlation with composite dropout probability.
              </p>
            </div>
            {marksCorr && (
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-cream-100 dark:bg-charcoal-750 text-clay-600 dark:text-clay-400 border border-sand-200 dark:border-charcoal-700">
                Pearson r: {marksCorr.correlation_r?.toFixed(2) || '0.00'}
              </span>
            )}
          </div>

          <div className="h-64 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EADBC8" opacity={0.5} />
                <XAxis
                  type="number"
                  dataKey="x"
                  name="Marks"
                  unit="%"
                  domain={[0, 100]}
                  tick={{ fontSize: 11, fill: '#4A3B32' }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name="Risk Score"
                  unit="%"
                  domain={[0, 100]}
                  tick={{ fontSize: 11, fill: '#4A3B32' }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  contentStyle={{
                    backgroundColor: '#FFFBF5',
                    borderRadius: '12px',
                    borderColor: '#EADBC8',
                    fontSize: '12px',
                  }}
                />
                <Scatter name="Students" data={marksCorr?.data_points || []} fill="#5E8C6E" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
