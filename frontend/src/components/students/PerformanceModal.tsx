import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { studentApi } from '../../api/students';
import type { PerformanceRecord } from '../../types';
import { useToast } from '../../context/ToastContext';
import { Loader2 } from 'lucide-react';

interface PerformanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  studentId: string;
  studentName: string;
  existingPerformance?: PerformanceRecord | null;
  onSaved: () => void;
}

export const PerformanceModal: React.FC<PerformanceModalProps> = ({
  isOpen,
  onClose,
  studentId,
  studentName,
  existingPerformance,
  onSaved,
}) => {
  const { success, error, warning } = useToast();

  const [semester, setSemester] = useState<number>(existingPerformance?.semester || 1);
  const [academicYear, setAcademicYear] = useState<string>(
    existingPerformance?.academic_year || '2024-25'
  );
  const [attendance, setAttendance] = useState<string>(
    existingPerformance?.attendance?.toString() || '85.0'
  );
  const [classesHeld, setClassesHeld] = useState<string>(
    existingPerformance?.classes_held?.toString() || '100'
  );
  const [marks, setMarks] = useState<string>(
    existingPerformance?.marks?.toString() || '75.0'
  );
  const [backlogs, setBacklogs] = useState<string>(
    existingPerformance?.backlogs?.toString() || '0'
  );
  const [assignments, setAssignments] = useState<string>(
    existingPerformance?.assignments?.toString() || '80.0'
  );
  const [engagement, setEngagement] = useState<string>(
    existingPerformance?.engagement?.toString() || '80.0'
  );
  const [saving, setSaving] = useState<boolean>(false);

  useEffect(() => {
    if (existingPerformance) {
      setSemester(existingPerformance.semester);
      setAcademicYear(existingPerformance.academic_year);
      setAttendance(existingPerformance.attendance.toString());
      setClassesHeld(existingPerformance.classes_held.toString());
      setMarks(existingPerformance.marks?.toString() || '');
      setBacklogs(existingPerformance.backlogs?.toString() || '0');
      setAssignments(existingPerformance.assignments?.toString() || '');
      setEngagement(existingPerformance.engagement?.toString() || '');
    }
  }, [existingPerformance]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    try {
      const attNum = parseFloat(attendance);
      const heldNum = parseInt(classesHeld, 10);
      const marksNum = marks ? parseFloat(marks) : undefined;
      const backlogsNum = backlogs ? parseInt(backlogs, 10) : 0;
      const assignNum = assignments ? parseFloat(assignments) : undefined;
      const engNum = engagement ? parseFloat(engagement) : undefined;

      if (isNaN(attNum) || attNum < 0 || attNum > 100) {
        throw new Error('Attendance must be between 0 and 100%');
      }

      await studentApi.upsertPerformance(
        studentId,
        semester,
        {
          attendance: attNum,
          classes_held: heldNum,
          marks: marksNum,
          backlogs: backlogsNum,
          assignments: assignNum,
          engagement: engNum,
          academic_year: academicYear,
        },
        existingPerformance?.version
      );

      success('Performance Updated', 'Risk assessment recomputed in real time.');
      onSaved();
      onClose();
    } catch (err: unknown) {
      const statusCode = err && typeof err === 'object' && 'status' in err ? (err as { status: number }).status : 0;
      if (statusCode === 409 || statusCode === 412) {
        warning(
          'Concurrent Modification Detected',
          'This record was edited by another instructor. Please refresh to load latest values.'
        );
      } else {
        const msg = err instanceof Error ? err.message : 'Failed to update performance';
        error('Update Failed', msg);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Update Performance — ${studentName}`}
      description="Updating academic records triggers automated risk reassessment and notifications."
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Semester
            </label>
            <input
              type="number"
              min="1"
              max="12"
              required
              disabled={!!existingPerformance}
              value={semester}
              onChange={(e) => setSemester(parseInt(e.target.value, 10))}
              className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 disabled:opacity-60"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Academic Year
            </label>
            <input
              type="text"
              required
              value={academicYear}
              onChange={(e) => setAcademicYear(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Attendance (%) *
            </label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="100"
              required
              value={attendance}
              onChange={(e) => setAttendance(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Classes Held *
            </label>
            <input
              type="number"
              min="1"
              required
              value={classesHeld}
              onChange={(e) => setClassesHeld(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Aggregate Marks (%)
            </label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="100"
              value={marks}
              onChange={(e) => setMarks(e.target.value)}
              placeholder="e.g. 72.5"
              className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Active Backlogs
            </label>
            <input
              type="number"
              min="0"
              max="20"
              value={backlogs}
              onChange={(e) => setBacklogs(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Assignment Submission (%)
            </label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="100"
              value={assignments}
              onChange={(e) => setAssignments(e.target.value)}
              placeholder="Optional"
              className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              LMS Engagement (0–100)
            </label>
            <input
              type="number"
              step="1"
              min="0"
              max="100"
              value={engagement}
              onChange={(e) => setEngagement(e.target.value)}
              placeholder="Optional"
              className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100"
            />
          </div>
        </div>

        <div className="pt-4 flex justify-end space-x-3 border-t border-sand-200 dark:border-charcoal-700">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 text-ink-700 dark:text-sand-300 text-sm font-medium hover:bg-sand-100 dark:hover:bg-charcoal-800 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-sm font-semibold shadow-soft card-lift disabled:opacity-60 transition-all"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...
              </>
            ) : (
              'Save & Recompute Risk'
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
};
