import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { useToast } from '../../context/ToastContext';
import { GraduationCap, Lock, Mail, User, Building, Loader2, ArrowRight, Eye, EyeOff } from 'lucide-react';

export const RegisterPage: React.FC = () => {
  const { success, error } = useToast();
  const navigate = useNavigate();

  const [name, setName] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [role, setRole] = useState<'teacher' | 'hod' | 'student'>('teacher');
  const [erpId, setErpId] = useState<string>('');
  const [department, setDepartment] = useState<string>('Computer Science');
  const [phone, setPhone] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  // Password strength check (Backend security policy requires min 10 characters)
  const hasMinLength = password.length >= 10;
  const hasUpperLower = /[a-z]/.test(password) && /[A-Z]/.test(password);
  const hasDigitOrSpecial = /[\d\W]/.test(password);
  const passwordValid = hasMinLength && hasUpperLower && hasDigitOrSpecial;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!passwordValid) {
      error('Password Requirements', 'Password must meet complexity criteria (min 10 characters, upper/lower, number/symbol).');
      return;
    }

    setLoading(true);
    try {
      await authApi.register({
        name,
        email,
        password,
        role,
        erp_id: role === 'student' ? erpId : undefined,
        department: role !== 'student' ? department : undefined,
        phone: phone.trim() ? phone : undefined,
        phone_e164: phone.trim() ? phone : undefined,
      });

      success('Registration Submitted', 'Verification link sent to your institutional email.');
      navigate(`/verify-email?email=${encodeURIComponent(email)}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Registration failed';
      error('Registration Error', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-cream-50 dark:bg-charcoal-900">
      <div className="w-full max-w-lg bg-white dark:bg-charcoal-850 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-8 shadow-lift animate-fade-up">
        <div className="text-center space-y-2 mb-6">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-clay-500 text-white items-center justify-center shadow-soft mb-2">
            <GraduationCap className="w-7 h-7" />
          </div>
          <h2 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100">
            Create an Account
          </h2>
          <p className="text-xs text-ink-500 dark:text-sand-400">
            Join the Beacon academic early intervention platform
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Role Selection */}
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1.5">
              Institutional Role
            </label>
            <div className="grid grid-cols-3 gap-2">
              {(['teacher', 'hod', 'student'] as const).map((r) => (
                <button
                  type="button"
                  key={r}
                  onClick={() => setRole(r)}
                  className={`py-2 text-xs font-semibold rounded-xl border capitalize transition-all ${
                    role === r
                      ? 'bg-clay-500 text-white border-clay-500 shadow-soft'
                      : 'bg-cream-50 dark:bg-charcoal-800 text-ink-700 dark:text-sand-300 border-sand-300 dark:border-charcoal-700 hover:bg-sand-100'
                  }`}
                >
                  {r === 'hod' ? 'HOD' : r}
                </button>
              ))}
            </div>
            {role !== 'student' && (
              <p className="mt-2 text-[11px] text-ink-500 dark:text-sand-400 bg-sand-100/70 dark:bg-charcoal-800 p-2 rounded-lg border border-sand-200 dark:border-charcoal-700">
                ℹ️ <strong>Institutional Security:</strong> Faculty & HOD accounts require email verification and Administrator approval before first login.
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Full Name
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
                <User className="w-4 h-4" />
              </div>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Dr. Eleanor Vance"
                className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Institutional Email
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
                <Mail className="w-4 h-4" />
              </div>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@university.edu"
                className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
              />
            </div>
          </div>

          {role === 'student' ? (
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                Student ERP ID *
              </label>
              <input
                type="text"
                required
                value={erpId}
                onChange={(e) => setErpId(e.target.value)}
                placeholder="e.g. CS2024-001"
                className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                Academic Department
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
                  <Building className="w-4 h-4" />
                </div>
                <select
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                >
                  <option value="Computer Science">Computer Science</option>
                  <option value="Electronics">Electronics</option>
                  <option value="Mechanical">Mechanical</option>
                  <option value="Civil">Civil</option>
                </select>
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Phone Number (Optional for SMS Reset)
            </label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+919876543210"
              className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-9 pr-10 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-ink-400 hover:text-ink-600 dark:hover:text-sand-200 transition-colors focus:outline-none"
                title={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            {/* Password strength indicators */}
            <div className="mt-2 grid grid-cols-3 gap-1.5 text-[10px]">
              <div
                className={`px-2 py-1 rounded text-center font-medium ${
                  hasMinLength
                    ? 'bg-sage-100 text-sage-600'
                    : 'bg-sand-200 dark:bg-charcoal-700 text-ink-500'
                }`}
              >
                10+ Characters
              </div>
              <div
                className={`px-2 py-1 rounded text-center font-medium ${
                  hasUpperLower
                    ? 'bg-sage-100 text-sage-600'
                    : 'bg-sand-200 dark:bg-charcoal-700 text-ink-500'
                }`}
              >
                Upper & Lower
              </div>
              <div
                className={`px-2 py-1 rounded text-center font-medium ${
                  hasDigitOrSpecial
                    ? 'bg-sage-100 text-sage-600'
                    : 'bg-sand-200 dark:bg-charcoal-700 text-ink-500'
                }`}
              >
                Number / Symbol
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !passwordValid}
            className="w-full mt-4 py-2.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white font-semibold text-sm shadow-soft card-lift flex items-center justify-center disabled:opacity-60 transition-all"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Registering...
              </>
            ) : (
              <>
                Complete Registration <ArrowRight className="w-4 h-4 ml-1.5" />
              </>
            )}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-sand-200 dark:border-charcoal-700 text-center">
          <p className="text-xs text-ink-500 dark:text-sand-400">
            Already registered?{' '}
            <Link to="/login" className="font-semibold text-clay-500 hover:text-clay-600">
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};
