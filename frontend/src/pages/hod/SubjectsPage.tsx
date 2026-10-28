import React, { useState, useEffect, useCallback } from 'react';
import { subjectApi, type SubjectItem, type CreateSubjectPayload } from '../../api/subjects';
import { hodApi, type TeacherItem } from '../../api/hod';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import {
  BookOpen,
  Plus,
  UserCheck,
  Search,
  RefreshCw,
  Trash2,
  Calendar,
  Layers,
  GraduationCap,
  X,
} from 'lucide-react';

export const SubjectsPage: React.FC = () => {
  const { user } = useAuth();
  const { success, error } = useToast();

  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [teachers, setTeachers] = useState<TeacherItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [semesterFilter, setSemesterFilter] = useState<string>('');

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [assignSubjectModal, setAssignSubjectModal] = useState<SubjectItem | null>(null);
  const [selectedTeacherId, setSelectedTeacherId] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Form State for Add Subject
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    department: user?.department || 'Computer Science',
    year: '3rd Year',
    semester: 5,
    credits: 4,
    academic_year: '2024-25',
    assigned_teacher_id: '',
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [subs, teachersList] = await Promise.all([
        subjectApi.listSubjects({
          department: user?.role === 'hod' ? (user?.department || undefined) : undefined,
          semester: semesterFilter ? parseInt(semesterFilter, 10) : undefined,
        }),
        hodApi.listTeachers(),
      ]);
      setSubjects(subs);
      setTeachers(teachersList);
    } catch (err: any) {
      console.error(err);
      error('Failed to Load', err.message || 'Could not fetch subjects or faculty list.');
    } finally {
      setLoading(false);
    }
  }, [error, semesterFilter, user?.department, user?.role]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreateSubject = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload: CreateSubjectPayload = {
        name: formData.name,
        code: formData.code.toUpperCase(),
        department: formData.department,
        year: formData.year,
        semester: Number(formData.semester),
        credits: Number(formData.credits),
        academic_year: formData.academic_year,
        assigned_teacher_id: formData.assigned_teacher_id || null,
      };

      await subjectApi.createSubject(payload);
      success('Subject Created', `${formData.name} (${formData.code}) has been added.`);
      setIsAddModalOpen(false);
      setFormData({
        name: '',
        code: '',
        department: user?.department || 'Computer Science',
        year: '3rd Year',
        semester: 5,
        credits: 4,
        academic_year: '2024-25',
        assigned_teacher_id: '',
      });
      fetchData();
    } catch (err: any) {
      error('Creation Failed', err.message || 'Failed to create subject.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAssignTeacher = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignSubjectModal || !selectedTeacherId) return;

    setSubmitting(true);
    try {
      await subjectApi.assignTeacher(assignSubjectModal.id, selectedTeacherId);
      const teacherObj = teachers.find((t) => t.id === selectedTeacherId);
      success(
        'Faculty Assigned',
        `${assignSubjectModal.name} successfully assigned to ${teacherObj?.name || 'teacher'}.`
      );
      setAssignSubjectModal(null);
      setSelectedTeacherId('');
      fetchData();
    } catch (err: any) {
      error('Assignment Failed', err.message || 'Could not assign faculty to subject.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteSubject = async (subject: SubjectItem) => {
    if (!confirm(`Are you sure you want to delete ${subject.name} (${subject.code})?`)) return;
    try {
      await subjectApi.deleteSubject(subject.id);
      success('Deleted', `Subject ${subject.name} removed.`);
      setSubjects((prev) => prev.filter((s) => s.id !== subject.id));
    } catch (err: any) {
      error('Delete Failed', err.message || 'Failed to delete subject.');
    }
  };

  const filteredSubjects = subjects.filter((s) => {
    const matchesSearch =
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.code.toLowerCase().includes(search.toLowerCase()) ||
      (s.assigned_teacher_name && s.assigned_teacher_name.toLowerCase().includes(search.toLowerCase()));
    return matchesSearch;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-sand-200 dark:border-charcoal-800">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink-900 dark:text-sand-100 flex items-center">
            <BookOpen className="w-8 h-8 mr-3 text-clay-500" />
            Curriculum & Subject Assignments
          </h1>
          <p className="text-xs sm:text-sm text-ink-500 dark:text-sand-400 mt-1">
            Departmental subjects governance: create curriculum courses and assign dedicated professors (HOD &rarr; Teacher &rarr; Subject).
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center px-3.5 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs font-semibold text-ink-700 dark:text-sand-300 hover:bg-sand-50 dark:hover:bg-charcoal-750 transition-all shadow-soft"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            Create Subject
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by subject name, code (e.g. CS601), or assigned professor..."
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
          />
        </div>

        <select
          value={semesterFilter}
          onChange={(e) => setSemesterFilter(e.target.value)}
          className="px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
        >
          <option value="">All Semesters</option>
          {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
            <option key={s} value={s}>
              Semester {s}
            </option>
          ))}
        </select>
      </div>

      {/* Subjects Grid */}
      {loading ? (
        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-12 text-center text-xs text-ink-500 dark:text-sand-400">
          Loading curriculum subjects...
        </div>
      ) : filteredSubjects.length === 0 ? (
        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-12 text-center text-xs text-ink-500 dark:text-sand-400">
          No subjects found. Click <strong>Create Subject</strong> to add your department curriculum.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredSubjects.map((sub) => {
            const hasAssignedTeacher = !!sub.assigned_teacher_id;

            return (
              <div
                key={sub.id}
                className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-5 shadow-soft hover:shadow-lift transition-all flex flex-col justify-between"
              >
                <div>
                  {/* Top Bar: Code & Credits */}
                  <div className="flex items-start justify-between">
                    <span className="font-mono text-xs font-bold px-2.5 py-1 rounded-lg bg-clay-50 dark:bg-charcoal-700 text-clay-700 dark:text-clay-300 border border-clay-200 dark:border-charcoal-600">
                      {sub.code}
                    </span>
                    <span className="text-[11px] font-semibold text-ink-500 dark:text-sand-400 bg-sand-100 dark:bg-charcoal-750 px-2 py-0.5 rounded-md">
                      {sub.credits} Credits
                    </span>
                  </div>

                  <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 mt-3 line-clamp-1">
                    {sub.name}
                  </h3>

                  <div className="mt-2 space-y-1 text-xs text-ink-500 dark:text-sand-400">
                    <div className="flex items-center">
                      <Layers className="w-3.5 h-3.5 mr-1.5 text-ink-400" />
                      <span>{sub.department} &bull; {sub.year}</span>
                    </div>
                    <div className="flex items-center">
                      <Calendar className="w-3.5 h-3.5 mr-1.5 text-ink-400" />
                      <span>Semester {sub.semester} &bull; AY {sub.academic_year}</span>
                    </div>
                  </div>

                  {/* Faculty Assignment Badge */}
                  <div className="mt-4 p-3 rounded-xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-ink-400 dark:text-sand-500 block mb-1">
                      Assigned Faculty
                    </span>
                    {hasAssignedTeacher ? (
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <GraduationCap className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                          <span className="font-semibold text-xs text-ink-900 dark:text-sand-100">
                            {sub.assigned_teacher_name || 'Assigned Professor'}
                          </span>
                        </div>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400 font-bold">
                          Assigned
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-rose-600 dark:text-rose-400 italic">
                          No professor assigned
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-400 font-bold">
                          Unassigned
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Actions */}
                <div className="mt-5 pt-3 border-t border-sand-100 dark:border-charcoal-700 flex items-center justify-between">
                  <button
                    onClick={() => {
                      setAssignSubjectModal(sub);
                      setSelectedTeacherId(sub.assigned_teacher_id || '');
                    }}
                    className="inline-flex items-center px-3 py-1.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
                  >
                    <UserCheck className="w-3.5 h-3.5 mr-1.5" />
                    {hasAssignedTeacher ? 'Reassign Teacher' : 'Assign Teacher'}
                  </button>

                  <button
                    onClick={() => handleDeleteSubject(sub)}
                    className="p-1.5 rounded-xl text-ink-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors"
                    title="Delete Subject"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal: Create Subject */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-charcoal-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 shadow-2xl w-full max-w-lg overflow-hidden animate-scale-up">
            <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between bg-cream-50 dark:bg-charcoal-850">
              <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 flex items-center">
                <Plus className="w-5 h-5 mr-2 text-clay-500" />
                Add New Subject to Curriculum
              </h3>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-ink-400 hover:text-ink-600 dark:hover:text-sand-200 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubject} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                  Subject Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Machine Learning & Pattern Recognition"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Subject Code *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                    placeholder="e.g. CS601"
                    className="w-full px-3 py-2 text-xs uppercase font-mono rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Credits *
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    required
                    value={formData.credits}
                    onChange={(e) => setFormData({ ...formData, credits: parseInt(e.target.value, 10) })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Year Level
                  </label>
                  <select
                    value={formData.year}
                    onChange={(e) => setFormData({ ...formData, year: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  >
                    <option value="1st Year">1st Year</option>
                    <option value="2nd Year">2nd Year</option>
                    <option value="3rd Year">3rd Year</option>
                    <option value="4th Year">4th Year</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Semester *
                  </label>
                  <select
                    value={formData.semester}
                    onChange={(e) => setFormData({ ...formData, semester: parseInt(e.target.value, 10) })}
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

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Department
                  </label>
                  <input
                    type="text"
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Academic Year
                  </label>
                  <input
                    type="text"
                    value={formData.academic_year}
                    onChange={(e) => setFormData({ ...formData, academic_year: e.target.value })}
                    placeholder="2024-25"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                  Assign Teaching Faculty (Optional)
                </label>
                <select
                  value={formData.assigned_teacher_id}
                  onChange={(e) => setFormData({ ...formData, assigned_teacher_id: e.target.value })}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                >
                  <option value="">-- Leave Unassigned for now --</option>
                  {teachers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.department || 'Faculty'})
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-4 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-ink-600 dark:text-sand-300 hover:bg-sand-100 dark:hover:bg-charcoal-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift disabled:opacity-50"
                >
                  {submitting ? 'Creating...' : 'Create Subject'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Assign Subject to Teacher */}
      {assignSubjectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-charcoal-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 shadow-2xl w-full max-w-md overflow-hidden animate-scale-up">
            <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between bg-cream-50 dark:bg-charcoal-850">
              <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 flex items-center">
                <UserCheck className="w-5 h-5 mr-2 text-clay-500" />
                Assign Subject to Faculty
              </h3>
              <button
                onClick={() => setAssignSubjectModal(null)}
                className="text-ink-400 hover:text-ink-600 dark:hover:text-sand-200 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAssignTeacher} className="p-6 space-y-4">
              <div className="p-3 rounded-xl bg-sand-50 dark:bg-charcoal-750 border border-sand-200 dark:border-charcoal-700">
                <span className="font-mono text-xs font-bold text-clay-600 dark:text-clay-400">
                  {assignSubjectModal.code}
                </span>
                <p className="font-semibold text-sm text-ink-900 dark:text-sand-100 mt-0.5">
                  {assignSubjectModal.name}
                </p>
                <p className="text-xs text-ink-500 dark:text-sand-400">
                  {assignSubjectModal.department} &bull; Semester {assignSubjectModal.semester}
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                  Select Professor *
                </label>
                <select
                  required
                  value={selectedTeacherId}
                  onChange={(e) => setSelectedTeacherId(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                >
                  <option value="">-- Choose a teacher from department --</option>
                  {teachers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.email})
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-3 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setAssignSubjectModal(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-ink-600 dark:text-sand-300 hover:bg-sand-100 dark:hover:bg-charcoal-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !selectedTeacherId}
                  className="px-5 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift disabled:opacity-50"
                >
                  {submitting ? 'Assigning...' : 'Confirm Assignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
