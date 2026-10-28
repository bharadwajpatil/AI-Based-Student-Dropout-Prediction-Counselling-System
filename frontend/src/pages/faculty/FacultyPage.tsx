import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { studentApi, type FacultyMember } from '../../api/students';
import { hodApi, type CreateTeacherPayload } from '../../api/hod';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { TeacherRosterModal } from '../../components/faculty/TeacherRosterModal';
import { AssignStudentsModal } from '../../components/faculty/AssignStudentsModal';
import {
  Users,
  GraduationCap,
  Search,
  UserPlus,
  Eye,
  CheckCircle2,
  BarChart,
  RefreshCw,
  Lock,
  X,
} from 'lucide-react';

export const FacultyPage: React.FC = () => {
  const { user, hasRole } = useAuth();
  const { success, error } = useToast();

  const [faculty, setFaculty] = useState<FacultyMember[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [department, setDepartment] = useState<string>(user?.department || '');
  const [search, setSearch] = useState<string>('');

  // Modals state
  const [rosterTeacher, setRosterTeacher] = useState<FacultyMember | null>(null);
  const [assignTeacher, setAssignTeacher] = useState<FacultyMember | null>(null);
  const [isAddTeacherOpen, setIsAddTeacherOpen] = useState<boolean>(false);
  const [addingTeacher, setAddingTeacher] = useState<boolean>(false);
  const [teacherForm, setTeacherForm] = useState({
    name: '',
    email: '',
    phone: '',
    employee_id: '',
    department: user?.department || 'Computer Science',
    designation: 'Assistant Professor',
    password: '',
    confirm_password: '',
  });

  const fetchFaculty = useCallback(async () => {
    setLoading(true);
    try {
      const data = await studentApi.listFaculty(department || undefined);
      setFaculty(data);
    } catch (err) {
      console.error('Failed to load faculty', err);
      error('Error', 'Unable to fetch faculty members.');
    } finally {
      setLoading(false);
    }
  }, [department, error]);

  useEffect(() => {
    fetchFaculty();
  }, [fetchFaculty]);

  const filteredFaculty = useMemo(() => {
    if (!search.trim()) return faculty;
    const query = search.toLowerCase();
    return faculty.filter(
      (f) =>
        f.name.toLowerCase().includes(query) ||
        f.email.toLowerCase().includes(query) ||
        (f.department && f.department.toLowerCase().includes(query))
    );
  }, [faculty, search]);

  const totalAssigned = useMemo(() => {
    return faculty.reduce((acc, f) => acc + (f.assigned_student_count || 0), 0);
  }, [faculty]);

  const avgPerMentor = useMemo(() => {
    if (faculty.length === 0) return 0;
    return Math.round(totalAssigned / faculty.length);
  }, [totalAssigned, faculty.length]);

  const handleCreateTeacher = async (e: React.FormEvent) => {
    e.preventDefault();
    if (teacherForm.password !== teacherForm.confirm_password) {
      error('Validation Error', 'Passwords do not match.');
      return;
    }
    if (teacherForm.password.length < 8) {
      error('Validation Error', 'Password must be at least 8 characters long.');
      return;
    }

    setAddingTeacher(true);
    try {
      const payload: CreateTeacherPayload = {
        name: teacherForm.name,
        email: teacherForm.email,
        phone: teacherForm.phone || undefined,
        employee_id: teacherForm.employee_id || undefined,
        department: teacherForm.department,
        designation: teacherForm.designation || undefined,
        password: teacherForm.password,
      };

      await hodApi.createTeacher(payload);
      success('Teacher Created', `Faculty account created for ${teacherForm.name}.`);
      setIsAddTeacherOpen(false);
      setTeacherForm({
        name: '',
        email: '',
        phone: '',
        employee_id: '',
        department: user?.department || 'Computer Science',
        designation: 'Assistant Professor',
        password: '',
        confirm_password: '',
      });
      fetchFaculty();
    } catch (err: any) {
      error('Creation Failed', err.message || 'Could not register teacher.');
    } finally {
      setAddingTeacher(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-sand-200 dark:border-charcoal-800">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100 flex items-center">
            <GraduationCap className="w-7 h-7 mr-2 text-clay-500" />
            Faculty & Mentorship Workload
          </h1>
          <p className="text-xs sm:text-sm text-ink-500 dark:text-sand-400 mt-1">
            Section 5: HOD & Admin governance &mdash; create teachers, inspect assigned cohorts, and balance mentorship distribution.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchFaculty}
            disabled={loading}
            className="inline-flex items-center px-3.5 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs font-semibold text-ink-700 dark:text-sand-300 hover:bg-sand-50 dark:hover:bg-charcoal-750 transition-all shadow-soft"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          {hasRole(['admin', 'hod']) && (
            <button
              onClick={() => setIsAddTeacherOpen(true)}
              className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
            >
              <UserPlus className="w-4 h-4 mr-1.5" />
              Add New Teacher
            </button>
          )}
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-5 shadow-soft">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-500 dark:text-sand-400 uppercase tracking-wider">
              Total Faculty
            </span>
            <div className="w-8 h-8 rounded-lg bg-clay-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 flex items-center justify-center">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100 mt-2">
            {faculty.length}
          </p>
          <p className="text-[11px] text-ink-400 dark:text-sand-500 mt-1">
            Active mentoring professors
          </p>
        </div>

        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-5 shadow-soft">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-500 dark:text-sand-400 uppercase tracking-wider">
              Total Assigned Students
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100 mt-2">
            {totalAssigned}
          </p>
          <p className="text-[11px] text-ink-400 dark:text-sand-500 mt-1">
            Students under active faculty mentorship
          </p>
        </div>

        <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-5 shadow-soft">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-500 dark:text-sand-400 uppercase tracking-wider">
              Avg Workload
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 flex items-center justify-center">
              <BarChart className="w-4 h-4" />
            </div>
          </div>
          <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100 mt-2">
            {avgPerMentor} <span className="text-xs font-normal text-ink-500 dark:text-sand-400">students / faculty</span>
          </p>
          <p className="text-[11px] text-ink-400 dark:text-sand-500 mt-1">
            Department cohort distribution
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search faculty by name or email (e.g. bharadwaj)..."
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
          />
        </div>

        <select
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
          className="px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
        >
          <option value="">All Departments</option>
          <option value="Computer Science">Computer Science</option>
          <option value="Electronics">Electronics</option>
          <option value="Mechanical">Mechanical</option>
          <option value="Civil">Civil</option>
        </select>
      </div>

      {/* Faculty Cards Grid */}
      <div className="space-y-4">
        {loading ? (
          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-12 text-center text-xs text-ink-500 dark:text-sand-400">
            Loading faculty directory...
          </div>
        ) : filteredFaculty.length === 0 ? (
          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-12 text-center text-xs text-ink-500 dark:text-sand-400">
            No faculty members found for this filter criteria.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredFaculty.map((teacher) => {
              const count = teacher.assigned_student_count || 0;
              const isHeavy = count > 25;
              const isModerate = count >= 10 && count <= 25;

              return (
                <div
                  key={teacher.id}
                  className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-5 shadow-soft hover:shadow-lift transition-all flex flex-col justify-between"
                >
                  <div>
                    {/* Top Row: Avatar & Status */}
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-12 h-12 rounded-2xl bg-clay-500 text-white flex items-center justify-center font-bold text-lg shadow-soft">
                          {teacher.name?.[0]?.toUpperCase() || 'T'}
                        </div>
                        <div>
                          <h3 className="font-display font-bold text-ink-900 dark:text-sand-100 text-sm">
                            {teacher.name}
                          </h3>
                          <span className="text-[11px] text-ink-500 dark:text-sand-400 block truncate max-w-[180px]">
                            {teacher.email}
                          </span>
                        </div>
                      </div>

                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400">
                        Active
                      </span>
                    </div>

                    {/* Department Badge */}
                    <div className="mt-4 flex items-center justify-between text-xs">
                      <span className="text-ink-500 dark:text-sand-400">Department</span>
                      <span className="font-semibold text-ink-800 dark:text-sand-200 bg-sand-100 dark:bg-charcoal-750 px-2 py-0.5 rounded-md">
                        {teacher.department || 'Not Specified'}
                      </span>
                    </div>

                    {/* Workload Metric */}
                    <div className="mt-3 p-3 rounded-xl bg-cream-50 dark:bg-charcoal-850 border border-sand-200/80 dark:border-charcoal-700 flex items-center justify-between">
                      <div>
                        <span className="text-[11px] text-ink-500 dark:text-sand-400 block">
                          Assigned Students
                        </span>
                        <span className="text-xl font-display font-bold text-ink-900 dark:text-sand-100">
                          {count}
                        </span>
                      </div>

                      <div>
                        <span
                          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                            isHeavy
                              ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300'
                              : isModerate
                              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                              : 'bg-sand-200 text-ink-700 dark:bg-charcoal-700 dark:text-sand-300'
                          }`}
                        >
                          {isHeavy ? 'High Workload' : isModerate ? 'Active Cohort' : 'Light Workload'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="mt-5 pt-4 border-t border-sand-100 dark:border-charcoal-700 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setRosterTeacher(teacher)}
                      className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-xl bg-sand-100 hover:bg-sand-200 dark:bg-charcoal-700 dark:hover:bg-charcoal-650 text-ink-800 dark:text-sand-200 text-xs font-semibold transition-colors"
                    >
                      <Eye className="w-3.5 h-3.5 mr-1.5" />
                      View Students ({count})
                    </button>

                    <button
                      type="button"
                      onClick={() => setAssignTeacher(teacher)}
                      className="inline-flex items-center justify-center px-3.5 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
                      title="Assign students to this teacher"
                    >
                      <UserPlus className="w-3.5 h-3.5 mr-1" />
                      Add
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Roster Details Modal (View & Remove students) */}
      {rosterTeacher && (
        <TeacherRosterModal
          isOpen={!!rosterTeacher}
          onClose={() => setRosterTeacher(null)}
          teacher={rosterTeacher}
          onOpenAssign={() => setAssignTeacher(rosterTeacher)}
          onRosterChanged={() => fetchFaculty()}
        />
      )}

      {/* Assign Students Modal (Select & add students) */}
      {assignTeacher && (
        <AssignStudentsModal
          isOpen={!!assignTeacher}
          onClose={() => setAssignTeacher(null)}
          teacher={assignTeacher}
          onAssigned={() => {
            fetchFaculty();
            // If the roster modal is also viewing this teacher, refresh it
            if (rosterTeacher?.id === assignTeacher.id) {
              setRosterTeacher({ ...assignTeacher });
            }
          }}
        />
      )}

      {/* Modal: Create Teacher Account (Section 5) */}
      {isAddTeacherOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-charcoal-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 shadow-2xl w-full max-w-lg overflow-hidden animate-scale-up">
            <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between bg-cream-50 dark:bg-charcoal-850">
              <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 flex items-center">
                <UserPlus className="w-5 h-5 mr-2 text-clay-500" />
                Section 5: Add Faculty / Teacher Account
              </h3>
              <button
                onClick={() => setIsAddTeacherOpen(false)}
                className="text-ink-400 hover:text-ink-600 dark:hover:text-sand-200 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateTeacher} className="p-6 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={teacherForm.name}
                    onChange={(e) => setTeacherForm({ ...teacherForm, name: e.target.value })}
                    placeholder="e.g. Rahul Sharma"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Department *
                  </label>
                  <input
                    type="text"
                    required
                    value={teacherForm.department}
                    onChange={(e) => setTeacherForm({ ...teacherForm, department: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Email Address *
                  </label>
                  <input
                    type="email"
                    required
                    value={teacherForm.email}
                    onChange={(e) => setTeacherForm({ ...teacherForm, email: e.target.value })}
                    placeholder="rahul.sharma@university.edu"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Phone Number
                  </label>
                  <input
                    type="text"
                    value={teacherForm.phone}
                    onChange={(e) => setTeacherForm({ ...teacherForm, phone: e.target.value })}
                    placeholder="+91 9876543210"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Employee ID
                  </label>
                  <input
                    type="text"
                    value={teacherForm.employee_id}
                    onChange={(e) => setTeacherForm({ ...teacherForm, employee_id: e.target.value })}
                    placeholder="EMP-TEA-102"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Designation
                  </label>
                  <input
                    type="text"
                    value={teacherForm.designation}
                    onChange={(e) => setTeacherForm({ ...teacherForm, designation: e.target.value })}
                    placeholder="Assistant Professor"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-sand-200 dark:border-charcoal-700">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1 flex items-center">
                    <Lock className="w-3.5 h-3.5 mr-1 text-ink-400" />
                    Account Password *
                  </label>
                  <input
                    type="password"
                    required
                    value={teacherForm.password}
                    onChange={(e) => setTeacherForm({ ...teacherForm, password: e.target.value })}
                    placeholder="Minimum 8 characters"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1 flex items-center">
                    <Lock className="w-3.5 h-3.5 mr-1 text-ink-400" />
                    Confirm Password *
                  </label>
                  <input
                    type="password"
                    required
                    value={teacherForm.confirm_password}
                    onChange={(e) => setTeacherForm({ ...teacherForm, confirm_password: e.target.value })}
                    placeholder="Re-enter password"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              <p className="text-[11px] text-ink-400 dark:text-sand-500 pt-1">
                Account role will automatically be assigned as <code>teacher</code> and associated with this department.
              </p>

              <div className="pt-4 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsAddTeacherOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-ink-600 dark:text-sand-300 hover:bg-sand-100 dark:hover:bg-charcoal-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addingTeacher}
                  className="px-5 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift disabled:opacity-50"
                >
                  {addingTeacher ? 'Creating...' : 'Create Teacher Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
