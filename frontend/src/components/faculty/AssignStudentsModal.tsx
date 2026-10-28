import React, { useState, useEffect, useMemo } from 'react';
import { Modal } from '../common/Modal';
import { studentApi, type FacultyMember } from '../../api/students';
import type { Student } from '../../types';
import { useToast } from '../../context/ToastContext';
import { Search, UserCheck, Check, Filter } from 'lucide-react';

interface AssignStudentsModalProps {
  isOpen: boolean;
  onClose: () => void;
  teacher: FacultyMember;
  onAssigned: () => void;
}

export const AssignStudentsModal: React.FC<AssignStudentsModalProps> = ({
  isOpen,
  onClose,
  teacher,
  onAssigned,
}) => {
  const { success, error } = useToast();
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [search, setSearch] = useState<string>('');
  const [onlyUnassigned, setOnlyUnassigned] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      setSelectedIds([]);
      setSearch('');
      setLoading(true);

      // Fetch students for the teacher's department
      studentApi
        .listStudents({
          department: teacher.department,
          limit: 100,
        })
        .then((res) => {
          setStudents(res.items || []);
        })
        .catch((err) => {
          console.error('Failed to load students for assignment', err);
          error('Error', 'Unable to fetch departmental students.');
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, teacher.department, error]);

  const filteredStudents = useMemo(() => {
    return students.filter((s) => {
      // Exclude students who already have this teacher assigned
      const alreadyAssigned = s.assigned_teacher_ids?.includes(teacher.id);
      if (alreadyAssigned) return false;

      if (onlyUnassigned && (s.assigned_teacher_ids?.length ?? 0) > 0) {
        return false;
      }

      if (search.trim()) {
        const query = search.toLowerCase();
        const matchesName = s.name.toLowerCase().includes(query);
        const matchesErp = s.erp_id.toLowerCase().includes(query);
        return matchesName || matchesErp;
      }

      return true;
    });
  }, [students, teacher.id, onlyUnassigned, search]);

  const toggleStudent = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSelectAllVisible = () => {
    const visibleIds = filteredStudents.map((s) => s.id);
    const allSelected = visibleIds.every((id) => selectedIds.includes(id));
    if (allSelected) {
      setSelectedIds((prev) => prev.filter((id) => !visibleIds.includes(id)));
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...visibleIds])));
    }
  };

  const handleSubmit = async () => {
    if (selectedIds.length === 0) return;
    setSubmitting(true);
    try {
      const res = await studentApi.assignStudentsToFaculty(teacher.id, selectedIds);
      success(
        'Assignment Successful',
        `Assigned ${selectedIds.length} student(s) to ${teacher.name}. Total cohort: ${res.total_assigned}`
      );
      onAssigned();
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to assign students.';
      error('Assignment Failed', msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Assign Students to ${teacher.name}`}
      description={`Select students from ${teacher.department || 'the institution'} to assign under ${teacher.name}'s mentorship cohort.`}
      maxWidth="lg"
    >
      <div className="space-y-4">
        {/* Search & Filter Bar */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
              <Search className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by student name or ERP ID..."
              className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
            />
          </div>

          <label className="flex items-center space-x-2 text-xs font-medium text-ink-700 dark:text-sand-300 bg-sand-50 dark:bg-charcoal-800 px-3 py-2 rounded-xl border border-sand-200 dark:border-charcoal-700 cursor-pointer select-none">
            <Filter className="w-3.5 h-3.5 text-clay-500" />
            <input
              type="checkbox"
              checked={onlyUnassigned}
              onChange={(e) => setOnlyUnassigned(e.target.checked)}
              className="rounded text-clay-500 focus:ring-clay-400"
            />
            <span>Unassigned only</span>
          </label>
        </div>

        {/* Selection Stats and Select All */}
        <div className="flex items-center justify-between text-xs text-ink-500 dark:text-sand-400 px-1">
          <span>
            Found <strong>{filteredStudents.length}</strong> eligible student(s)
          </span>
          {filteredStudents.length > 0 && (
            <button
              type="button"
              onClick={handleSelectAllVisible}
              className="text-clay-600 dark:text-clay-400 font-semibold hover:underline"
            >
              {filteredStudents.every((s) => selectedIds.includes(s.id))
                ? 'Deselect all visible'
                : 'Select all visible'}
            </button>
          )}
        </div>

        {/* Student List */}
        <div className="max-h-72 overflow-y-auto space-y-2 pr-1 divide-y divide-sand-100 dark:divide-charcoal-800">
          {loading ? (
            <div className="py-12 text-center text-xs text-ink-500 dark:text-sand-400">
              Loading available students...
            </div>
          ) : filteredStudents.length === 0 ? (
            <div className="py-12 text-center text-xs text-ink-500 dark:text-sand-400">
              No eligible students found. All matching students may already be assigned to this teacher.
            </div>
          ) : (
            filteredStudents.map((s) => {
              const isSelected = selectedIds.includes(s.id);
              const mentorCount = s.assigned_teacher_ids?.length || 0;

              return (
                <div
                  key={s.id}
                  onClick={() => toggleStudent(s.id)}
                  className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'border-clay-500 bg-cream-50 dark:bg-charcoal-750/70 shadow-sm'
                      : 'border-sand-200 dark:border-charcoal-700 hover:bg-sand-50 dark:hover:bg-charcoal-800'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <div
                      className={`w-5 h-5 rounded-md flex items-center justify-center border transition-all ${
                        isSelected
                          ? 'bg-clay-500 border-clay-500 text-white'
                          : 'border-sand-400 dark:border-charcoal-600 bg-white dark:bg-charcoal-800'
                      }`}
                    >
                      {isSelected && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-semibold text-ink-900 dark:text-sand-100">
                          {s.name}
                        </span>
                        <span className="font-mono text-[11px] text-ink-500 dark:text-sand-400 bg-sand-100 dark:bg-charcoal-800 px-1.5 py-0.5 rounded">
                          {s.erp_id}
                        </span>
                      </div>
                      <p className="text-[11px] text-ink-500 dark:text-sand-400 mt-0.5">
                        Sem {s.semester} • {s.department} • Batch {s.batch}
                      </p>
                    </div>
                  </div>

                  <div>
                    {mentorCount === 0 ? (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                        Unassigned
                      </span>
                    ) : (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-sand-200 dark:bg-charcoal-700 text-ink-600 dark:text-sand-300">
                        {mentorCount} mentor{mentorCount > 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Bar */}
        <div className="flex items-center justify-between pt-3 border-t border-sand-200 dark:border-charcoal-700">
          <div className="text-xs font-medium text-ink-700 dark:text-sand-300">
            Selected: <strong className="text-clay-600 dark:text-clay-400">{selectedIds.length}</strong> student(s)
          </div>
          <div className="flex space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-ink-600 dark:text-sand-400 hover:bg-sand-100 dark:hover:bg-charcoal-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || selectedIds.length === 0}
              className="inline-flex items-center px-5 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft transition-all disabled:opacity-50"
            >
              <UserCheck className="w-4 h-4 mr-1.5" />
              {submitting ? 'Assigning...' : `Assign ${selectedIds.length} Student${selectedIds.length !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
