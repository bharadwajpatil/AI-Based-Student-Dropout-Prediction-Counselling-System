import React, { useState, useEffect, useCallback } from 'react';
import { adminApi, type HODItem, type CreateHODPayload, type AdminStats } from '../../api/admin';
import { useToast } from '../../context/ToastContext';
import {
  Users,
  UserPlus,
  Shield,
  Building,
  Mail,
  Phone,
  Search,
  RefreshCw,
  ToggleLeft,
  ToggleRight,
  GraduationCap,
  AlertTriangle,
  X,
  Lock,
} from 'lucide-react';

export const HodManagementPage: React.FC = () => {
  const { success, error } = useToast();

  const [hods, setHods] = useState<HODItem[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Form State for Add HOD
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    employee_id: '',
    department: 'Computer Science',
    designation: 'Head of Department',
    password: '',
    confirm_password: '',
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [hodList, adminStats] = await Promise.all([
        adminApi.listHods(),
        adminApi.getStats(),
      ]);
      setHods(hodList);
      setStats(adminStats);
    } catch (err: any) {
      console.error(err);
      error('Failed to Load', err.message || 'Could not fetch HOD directory.');
    } finally {
      setLoading(false);
    }
  }, [error]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleToggleStatus = async (hod: HODItem) => {
    const newStatus = hod.status === 'active' ? 'inactive' : 'active';
    try {
      await adminApi.toggleHodStatus(hod.id, newStatus);
      success('Status Updated', `${hod.name} is now ${newStatus}.`);
      setHods((prev) =>
        prev.map((h) => (h.id === hod.id ? { ...h, status: newStatus } : h))
      );
    } catch (err: any) {
      error('Error', err.message || 'Failed to update HOD status.');
    }
  };

  const handleCreateHod = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.password !== formData.confirm_password) {
      error('Validation Error', 'Passwords do not match.');
      return;
    }
    if (formData.password.length < 8) {
      error('Validation Error', 'Password must be at least 8 characters long.');
      return;
    }

    setSubmitting(true);
    try {
      const payload: CreateHODPayload = {
        name: formData.name,
        email: formData.email,
        phone: formData.phone || undefined,
        employee_id: formData.employee_id || undefined,
        department: formData.department,
        designation: formData.designation || undefined,
        password: formData.password,
      };

      await adminApi.createHod(payload);
      success('HOD Created', `Successfully assigned HOD role to ${formData.name}`);
      setIsModalOpen(false);
      setFormData({
        name: '',
        email: '',
        phone: '',
        employee_id: '',
        department: 'Computer Science',
        designation: 'Head of Department',
        password: '',
        confirm_password: '',
      });
      fetchData();
    } catch (err: any) {
      error('Creation Failed', err.message || 'Could not create HOD account.');
    } finally {
      setSubmitting(false);
    }
  };

  const filteredHods = hods.filter(
    (h) =>
      h.name.toLowerCase().includes(search.toLowerCase()) ||
      h.email.toLowerCase().includes(search.toLowerCase()) ||
      h.department.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-sand-200 dark:border-charcoal-800">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink-900 dark:text-sand-100 flex items-center">
            <Shield className="w-8 h-8 mr-3 text-clay-500" />
            Institutional Hierarchy — HOD Governance
          </h1>
          <p className="text-xs sm:text-sm text-ink-500 dark:text-sand-400 mt-1">
            Admin oversight: create department heads, activate/deactivate leadership credentials, and delegate faculty management.
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
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
          >
            <UserPlus className="w-4 h-4 mr-1.5" />
            Add New HOD
          </button>
        </div>
      </div>

      {/* Stats Summary Cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft">
            <span className="text-xs font-semibold text-ink-500 dark:text-sand-400 uppercase tracking-wider">
              Total HODs
            </span>
            <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100 mt-1">
              {stats.total_hods}
            </p>
            <p className="text-[11px] text-ink-400 dark:text-sand-500 mt-0.5">
              Active department heads
            </p>
          </div>

          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft">
            <span className="text-xs font-semibold text-ink-500 dark:text-sand-400 uppercase tracking-wider">
              Faculty / Teachers
            </span>
            <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100 mt-1">
              {stats.total_teachers}
            </p>
            <p className="text-[11px] text-ink-400 dark:text-sand-500 mt-0.5">
              Across {stats.departments.length} departments
            </p>
          </div>

          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft">
            <span className="text-xs font-semibold text-ink-500 dark:text-sand-400 uppercase tracking-wider">
              Total Students
            </span>
            <p className="font-display text-2xl font-bold text-ink-900 dark:text-sand-100 mt-1">
              {stats.total_students}
            </p>
            <p className="text-[11px] text-ink-400 dark:text-sand-500 mt-0.5">
              Enrolled students
            </p>
          </div>

          <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft">
            <span className="text-xs font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider flex items-center">
              <AlertTriangle className="w-3.5 h-3.5 mr-1" />
              High Risk / Backlogs
            </span>
            <p className="font-display text-2xl font-bold text-rose-600 dark:text-rose-400 mt-1">
              {stats.high_risk_students} <span className="text-xs font-normal text-ink-400">({stats.students_with_backlogs} with backlogs)</span>
            </p>
            <p className="text-[11px] text-ink-400 dark:text-sand-500 mt-0.5">
              Immediate intervention needed
            </p>
          </div>
        </div>
      )}

      {/* Search Bar */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft flex items-center gap-3">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search HOD by name, email, or department..."
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
          />
        </div>
      </div>

      {/* HOD Table */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden">
        <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between">
          <h2 className="font-display text-base font-bold text-ink-900 dark:text-sand-100 flex items-center">
            <Building className="w-4 h-4 mr-2 text-clay-500" />
            Heads of Department Directory
          </h2>
          <span className="text-xs text-ink-500 dark:text-sand-400 font-medium">
            {filteredHods.length} HOD{filteredHods.length !== 1 ? 's' : ''} registered
          </span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-xs text-ink-500 dark:text-sand-400">
            Loading department heads...
          </div>
        ) : filteredHods.length === 0 ? (
          <div className="p-12 text-center text-xs text-ink-500 dark:text-sand-400">
            No HOD accounts found matching your query.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-50 dark:bg-charcoal-850 text-ink-500 dark:text-sand-400 border-b border-sand-200 dark:border-charcoal-700">
                <tr>
                  <th className="px-5 py-3 font-semibold">Head of Department</th>
                  <th className="px-5 py-3 font-semibold">Department & Role</th>
                  <th className="px-5 py-3 font-semibold">Contact</th>
                  <th className="px-5 py-3 font-semibold">Teachers Managed</th>
                  <th className="px-5 py-3 font-semibold">Students</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-200 dark:divide-charcoal-750 text-ink-900 dark:text-sand-100">
                {filteredHods.map((hod) => (
                  <tr key={hod.id} className="hover:bg-sand-50/50 dark:hover:bg-charcoal-750/50 transition-colors">
                    <td className="px-5 py-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-9 h-9 rounded-xl bg-clay-100 dark:bg-charcoal-700 text-clay-700 dark:text-clay-300 font-bold flex items-center justify-center">
                          {hod.name[0]?.toUpperCase() || 'H'}
                        </div>
                        <div>
                          <p className="font-semibold">{hod.name}</p>
                          <p className="text-[11px] text-ink-400 dark:text-sand-500">
                            Emp ID: {hod.employee_id || 'N/A'}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="font-medium">{hod.department}</span>
                      <span className="block text-[11px] text-ink-400 dark:text-sand-500">
                        {hod.designation || 'Head of Department'}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="space-y-0.5">
                        <div className="flex items-center text-[11px] text-ink-600 dark:text-sand-300">
                          <Mail className="w-3 h-3 mr-1 text-ink-400" />
                          {hod.email}
                        </div>
                        {hod.phone && (
                          <div className="flex items-center text-[11px] text-ink-500 dark:text-sand-400">
                            <Phone className="w-3 h-3 mr-1 text-ink-400" />
                            {hod.phone}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300">
                        <GraduationCap className="w-3 h-3 mr-1" />
                        {hod.teachers_count} Teachers
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-sand-100 dark:bg-charcoal-700 text-ink-700 dark:text-sand-300">
                        <Users className="w-3 h-3 mr-1" />
                        {hod.students_count} Students
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                          hod.status === 'active'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400'
                            : 'bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-400'
                        }`}
                      >
                        {hod.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      <button
                        onClick={() => handleToggleStatus(hod)}
                        className={`inline-flex items-center px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                          hod.status === 'active'
                            ? 'text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30'
                            : 'text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/30'
                        }`}
                        title={hod.status === 'active' ? 'Deactivate HOD Account' : 'Activate HOD Account'}
                      >
                        {hod.status === 'active' ? (
                          <>
                            <ToggleRight className="w-4 h-4 mr-1 text-rose-500" />
                            Deactivate
                          </>
                        ) : (
                          <>
                            <ToggleLeft className="w-4 h-4 mr-1 text-emerald-500" />
                            Activate
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add HOD Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-charcoal-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-charcoal-800 rounded-3xl border border-sand-200 dark:border-charcoal-700 shadow-2xl w-full max-w-lg overflow-hidden animate-scale-up">
            <div className="px-6 py-4 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between bg-cream-50 dark:bg-charcoal-850">
              <h3 className="font-display font-bold text-base text-ink-900 dark:text-sand-100 flex items-center">
                <UserPlus className="w-5 h-5 mr-2 text-clay-500" />
                Register Head of Department (HOD)
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-ink-400 hover:text-ink-600 dark:hover:text-sand-200 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateHod} className="p-6 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g. Dr. Rajesh Sharma"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Department *
                  </label>
                  <select
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  >
                    <option value="Computer Science">Computer Science</option>
                    <option value="Information Technology">Information Technology</option>
                    <option value="Electronics & Telecommunication">Electronics & Telecommunication</option>
                    <option value="Mechanical Engineering">Mechanical Engineering</option>
                    <option value="Civil Engineering">Civil Engineering</option>
                    <option value="AI & Data Science">AI & Data Science</option>
                  </select>
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
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="hod.cs@university.edu"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Phone Number
                  </label>
                  <input
                    type="text"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
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
                    value={formData.employee_id}
                    onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
                    placeholder="EMP-HOD-101"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    Designation
                  </label>
                  <input
                    type="text"
                    value={formData.designation}
                    onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                    placeholder="Head of Department & Professor"
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
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
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
                    value={formData.confirm_password}
                    onChange={(e) => setFormData({ ...formData, confirm_password: e.target.value })}
                    placeholder="Re-enter password"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                  />
                </div>
              </div>

              <p className="text-[11px] text-ink-400 dark:text-sand-500 pt-1">
                Account role will automatically be assigned as <code>hod</code> with institutional access to teachers, subjects, and student cohorts.
              </p>

              <div className="pt-4 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-ink-600 dark:text-sand-300 hover:bg-sand-100 dark:hover:bg-charcoal-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift disabled:opacity-50"
                >
                  {submitting ? 'Registering...' : 'Register HOD Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
