import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Modal } from '../common/Modal';
import { studentApi, type FacultyMember } from '../../api/students';
import type { Student } from '../../types';
import { useToast } from '../../context/ToastContext';
import {
  Search,
  UserMinus,
  UserPlus,
  GraduationCap,
  ExternalLink,
  ShieldCheck,
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface TeacherRosterModalProps {
  isOpen: boolean;
  onClose: () => void;
  teacher: FacultyMember;
  onOpenAssign: () => void;
  onRosterChanged: () => void;
}

export const TeacherRosterModal: React.FC<TeacherRosterModalProps> = ({
  isOpen,
  onClose,
  teacher,
  onOpenAssign,
  onRosterChanged,
}) => {
  const { success, error } = useToast();
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [removingId, setRemovingId] = useState<string | null>(null);

  const fetchRoster = useCallback(async () => {
    if (!isOpen) return;
    setLoading(true);
    try {
      const res = await studentApi.listStudents({
        teacher_id: teacher.id,
        limit: 100,
      });
      setStudents(res.items || []);
    } catch (err) {
      console.error('Failed to load teacher roster', err);
      error('Error', 'Unable to fetch assigned students.');
    } finally {
      setLoading(false);
    }
  }, [isOpen, teacher.id, error]);

  useEffect(() => {
    fetchRoster();
  }, [fetchRoster]);

  const filteredStudents = useMemo(() => {
    if (!search.trim()) return students;
    const query = search.toLowerCase();
    return students.filter(
      (s) =>
        s.name.toLowerCase().includes(query) ||
        s.erp_id.toLowerCase().includes(query) ||
        (s.institutional_email && s.institutional_email.toLowerCase().includes(query))
    );
  }, [students, search]);

  const handleRemoveStudent = async (student: Student) => {
    if (!window.confirm(`Are you sure you want to remove ${student.name} (${student.erp_id}) from ${teacher.name}'s assigned cohort?`)) {
      return;
    }

    setRemovingId(student.id);
    try {
      await studentApi.unassignStudentFromFaculty(teacher.id, student.id);
      success('Student Removed', `${student.name} unassigned from ${teacher.name}.`);
      setStudents((prev) => prev.filter((s) => s.id !== student.id));
      onRosterChanged();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to unassign student.';
      error('Error', msg);
    } finally {
      setRemovingId(null);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${teacher.name}'s Assigned Students`}
      description={`Faculty mentor cohort for ${teacher.email} (${teacher.department || 'General Faculty'}).`}
      maxWidth="2xl"
    >
      <div className="space-y-4">
        {/* Teacher Snapshot Banner */}
        <div className="p-4 rounded-2xl bg-cream-100/70 dark:bg-charcoal-800 border border-sand-200 dark:border-charcoal-700 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-11 h-11 rounded-xl bg-clay-500/10 text-clay-600 dark:text-clay-400 flex items-center justify-center font-bold text-lg border border-clay-500/20">
              {teacher.name?.[0]?.toUpperCase() || 'F'}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h4 className="font-bold text-ink-900 dark:text-sand-100 text-sm">
                  {teacher.name}
                </h4>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-clay-100 text-clay-700 dark:bg-charcoal-700 dark:text-clay-400">
                  {teacher.department || 'Faculty'}
                </span>
              </div>
              <p className="text-xs text-ink-500 dark:text-sand-400">
                {teacher.email}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="text-right sm:text-right">
              <span className="text-xs text-ink-500 dark:text-sand-400 block">
                Total Assigned
              </span>
              <span className="text-base font-bold text-clay-600 dark:text-clay-400">
                {students.length} students
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                onClose();
                onOpenAssign();
              }}
              className="inline-flex items-center px-3 py-1.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft transition-all"
            >
              <UserPlus className="w-3.5 h-3.5 mr-1" /> Add Students
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search students in this roster by name or ERP ID..."
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
          />
        </div>

        {/* Assigned Student Roster List */}
        <div className="max-h-80 overflow-y-auto space-y-2 pr-1">
          {loading ? (
            <div className="py-12 text-center text-xs text-ink-500 dark:text-sand-400">
              Loading assigned students...
            </div>
          ) : filteredStudents.length === 0 ? (
            <div className="py-12 text-center text-xs text-ink-500 dark:text-sand-400">
              {students.length === 0
                ? 'No students currently assigned to this faculty member.'
                : 'No students match the current search query.'}
            </div>
          ) : (
            filteredStudents.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between p-3 rounded-xl border border-sand-200 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 hover:border-sand-300 dark:hover:border-charcoal-600 transition-all shadow-soft"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 rounded-lg bg-sand-100 dark:bg-charcoal-800 flex items-center justify-center text-ink-500 dark:text-sand-400 font-semibold text-xs">
                    <GraduationCap className="w-4 h-4 text-clay-500" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <Link
                        to={`/students/${s.id}`}
                        onClick={onClose}
                        className="text-xs font-bold text-ink-900 dark:text-sand-100 hover:text-clay-600 dark:hover:text-clay-400 inline-flex items-center group"
                      >
                        {s.name}
                        <ExternalLink className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </Link>
                      <span className="font-mono text-[11px] text-ink-500 dark:text-sand-400 bg-sand-100 dark:bg-charcoal-800 px-1.5 py-0.5 rounded">
                        {s.erp_id}
                      </span>
                    </div>
                    <p className="text-[11px] text-ink-500 dark:text-sand-400 mt-0.5">
                      Semester {s.semester} • Batch {s.batch}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 flex items-center">
                    <ShieldCheck className="w-3 h-3 mr-1" /> Active
                  </span>

                  <button
                    type="button"
                    onClick={() => handleRemoveStudent(s)}
                    disabled={removingId === s.id}
                    title="Remove student from this teacher's cohort"
                    className="p-1.5 rounded-lg text-rose-500 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors disabled:opacity-50"
                  >
                    <UserMinus className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center pt-3 border-t border-sand-200 dark:border-charcoal-700">
          <span className="text-xs text-ink-500 dark:text-sand-400">
            Showing <strong>{filteredStudents.length}</strong> of <strong>{students.length}</strong> students
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-ink-600 dark:text-sand-400 hover:bg-sand-100 dark:hover:bg-charcoal-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
};
