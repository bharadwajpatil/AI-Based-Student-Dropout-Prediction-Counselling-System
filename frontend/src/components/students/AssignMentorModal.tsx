import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { studentApi, type FacultyMember } from '../../api/students';
import type { Student } from '../../types';
import { useToast } from '../../context/ToastContext';
import { UserCheck, Check, Search, ShieldAlert } from 'lucide-react';

interface AssignMentorModalProps {
  isOpen: boolean;
  onClose: () => void;
  student: Student;
  onAssigned: (updated: Student) => void;
}

export const AssignMentorModal: React.FC<AssignMentorModalProps> = ({
  isOpen,
  onClose,
  student,
  onAssigned,
}) => {
  const { success, error } = useToast();
  const [faculty, setFaculty] = useState<FacultyMember[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [search, setSearch] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      setSelectedIds(student.assigned_teacher_ids || []);
      setSearch('');
      setLoading(true);
      studentApi
        .listFaculty()
        .then((data) => setFaculty(data))
        .catch((err) => {
          console.error('Failed to load faculty list', err);
          error('Error', 'Unable to load faculty members.');
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, student.assigned_teacher_ids, error]);

  const toggleTeacher = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await studentApi.updateStudent(student.id, {
        assigned_teacher_ids: selectedIds,
      });
      success('Faculty Assigned', `Assigned mentors updated for ${student.name}.`);
      onAssigned(updated);
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to update assigned faculty';
      error('Assignment Failed', msg);
    } finally {
      setSaving(false);
    }
  };

  const filteredFaculty = faculty.filter(
    (f) =>
      f.name.toLowerCase().includes(search.toLowerCase()) ||
      f.email.toLowerCase().includes(search.toLowerCase()) ||
      (f.department && f.department.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Assign Faculty Mentors"
      description={`Manage assigned faculty / teacher mentors for ${student.name} (${student.erp_id}).`}
      maxWidth="md"
    >
      <div className="space-y-4">
        {/* Search filter */}
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search faculty by name, email, or dept..."
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
          />
        </div>

        {/* Faculty List */}
        <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
          {loading ? (
            <div className="py-8 text-center text-xs text-ink-500 dark:text-sand-400">
              Loading faculty members...
            </div>
          ) : filteredFaculty.length === 0 ? (
            <div className="py-8 text-center text-xs text-ink-500 dark:text-sand-400">
              No faculty found matching search.
            </div>
          ) : (
            filteredFaculty.map((teacher) => {
              const isSelected = selectedIds.includes(teacher.id);
              const isSameDept = teacher.department === student.department;

              return (
                <div
                  key={teacher.id}
                  onClick={() => toggleTeacher(teacher.id)}
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
                        <p className="text-xs font-semibold text-ink-900 dark:text-sand-100">
                          {teacher.name}
                        </p>
                        {isSameDept && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-sand-200 dark:bg-charcoal-700 text-ink-700 dark:text-sand-300">
                            Dept Match
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-ink-500 dark:text-sand-400">
                        {teacher.email} {teacher.department ? `• ${teacher.department}` : ''}
                      </p>
                    </div>
                  </div>
                  <UserCheck
                    className={`w-4 h-4 ${
                      isSelected ? 'text-clay-500' : 'text-ink-300 dark:text-charcoal-600'
                    }`}
                  />
                </div>
              );
            })
          )}
        </div>

        {/* Selected Summary */}
        <div className="text-xs text-ink-600 dark:text-sand-400 pt-2 border-t border-sand-200 dark:border-charcoal-700 flex items-center justify-between">
          <span>
            <strong>{selectedIds.length}</strong> faculty mentor(s) selected
          </span>
          {selectedIds.length === 0 && (
            <span className="text-[11px] text-amber-600 flex items-center">
              <ShieldAlert className="w-3.5 h-3.5 mr-1" /> Unassigned student
            </span>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end space-x-3 pt-3">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-ink-600 dark:text-sand-400 hover:bg-sand-100 dark:hover:bg-charcoal-700 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft transition-all disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Assignment'}
          </button>
        </div>
      </div>
    </Modal>
  );
};
