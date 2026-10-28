import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { subjectApi, type SubjectItem } from '../../api/subjects';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import {
  BookOpen,
  GraduationCap,
  Layers,
  Calendar,
  RefreshCw,
  ClipboardList,
} from 'lucide-react';

export const TeacherSubjectsPage: React.FC = () => {
  const { user } = useAuth();
  const { error } = useToast();

  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchAssignedSubjects = useCallback(async () => {
    setLoading(true);
    try {
      const data = await subjectApi.getMyAssignedSubjects();
      setSubjects(data);
    } catch (err: any) {
      console.error(err);
      error('Failed to Load', err.message || 'Could not fetch your assigned subjects.');
    } finally {
      setLoading(false);
    }
  }, [error]);

  useEffect(() => {
    fetchAssignedSubjects();
  }, [fetchAssignedSubjects]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-sand-200 dark:border-charcoal-800">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink-900 dark:text-sand-100 flex items-center">
            <BookOpen className="w-8 h-8 mr-3 text-clay-500" />
            My Assigned Teaching Subjects
          </h1>
          <p className="text-xs sm:text-sm text-ink-500 dark:text-sand-400 mt-1">
            Courses allocated to you by your Department Head. Access subject grading sheets, record continuous assessment, and monitor student backlogs.
          </p>
        </div>

        <button
          onClick={fetchAssignedSubjects}
          disabled={loading}
          className="inline-flex items-center px-3.5 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs font-semibold text-ink-700 dark:text-sand-300 hover:bg-sand-50 dark:hover:bg-charcoal-750 transition-all shadow-soft"
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-12 text-center text-xs text-ink-500 dark:text-sand-400">
          Loading assigned courses...
        </div>
      ) : subjects.length === 0 ? (
        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-12 text-center space-y-3">
          <BookOpen className="w-12 h-12 text-ink-300 dark:text-sand-600 mx-auto" />
          <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100">
            No Subjects Assigned Yet
          </h3>
          <p className="text-xs text-ink-500 dark:text-sand-400 max-w-md mx-auto">
            Your Department Head (HOD) has not assigned any subjects to your profile yet. Please contact your HOD to assign your teaching courses.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {subjects.map((sub) => (
            <div
              key={sub.id}
              className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-6 shadow-soft hover:shadow-lift transition-all flex flex-col justify-between"
            >
              <div>
                {/* Subject Code badge and Credits */}
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold px-2.5 py-1 rounded-lg bg-clay-50 dark:bg-charcoal-700 text-clay-700 dark:text-clay-300 border border-clay-200 dark:border-charcoal-600">
                    {sub.code}
                  </span>
                  <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 bg-sand-100 dark:bg-charcoal-750 px-2 py-0.5 rounded-md">
                    {sub.credits} Credits
                  </span>
                </div>

                <h3 className="font-display font-bold text-lg text-ink-900 dark:text-sand-100 mt-3 line-clamp-1">
                  {sub.name}
                </h3>

                <div className="mt-3 space-y-1.5 text-xs text-ink-500 dark:text-sand-400">
                  <div className="flex items-center">
                    <Layers className="w-3.5 h-3.5 mr-2 text-ink-400" />
                    <span>{sub.department} &bull; {sub.year}</span>
                  </div>
                  <div className="flex items-center">
                    <Calendar className="w-3.5 h-3.5 mr-2 text-ink-400" />
                    <span>Semester {sub.semester} &bull; AY {sub.academic_year}</span>
                  </div>
                </div>

                <div className="mt-4 p-3 rounded-xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700 flex items-center justify-between text-xs">
                  <span className="text-ink-600 dark:text-sand-300 font-medium">Assigned Teacher</span>
                  <span className="font-semibold text-clay-600 dark:text-clay-400">
                    {sub.assigned_teacher_name || user?.first_name || 'You'}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-6 pt-4 border-t border-sand-100 dark:border-charcoal-700 flex items-center gap-3">
                <Link
                  to={`/teacher/marks?subject_id=${sub.id}`}
                  className="flex-1 inline-flex items-center justify-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
                >
                  <ClipboardList className="w-3.5 h-3.5 mr-1.5" />
                  Gradebook / Marks
                </Link>

                <Link
                  to={`/students?semester=${sub.semester}&department=${encodeURIComponent(sub.department)}`}
                  className="inline-flex items-center justify-center p-2 rounded-xl bg-sand-100 hover:bg-sand-200 dark:bg-charcoal-700 dark:hover:bg-charcoal-650 text-ink-700 dark:text-sand-200 text-xs font-semibold transition-colors"
                  title="View Enrolled Students"
                >
                  <GraduationCap className="w-4 h-4" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
