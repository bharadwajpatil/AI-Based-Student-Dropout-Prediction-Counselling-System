import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { GraduationCap, Lock, Mail, Loader2, ArrowRight, Eye, EyeOff } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const { success, error } = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const isExpired = searchParams.get('expired') === '1';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await login({ email, password });
      success('Welcome Back', 'Logged in successfully.');
      navigate('/');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Invalid credentials';
      error('Login Failed', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-cream-50 dark:bg-charcoal-900">
      <div className="w-full max-w-md bg-white dark:bg-charcoal-850 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-8 shadow-lift animate-fade-up">
        {/* Brand */}
        <div className="text-center space-y-2 mb-8">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-clay-500 text-white items-center justify-center shadow-soft mb-2">
            <GraduationCap className="w-7 h-7" />
          </div>
          <h2 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100">
            Welcome to Beacon
          </h2>
          <p className="text-xs text-ink-500 dark:text-sand-400">
            Student Dropout Early Warning & Intervention System
          </p>
        </div>

        {isExpired && (
          <div className="mb-6 p-3 rounded-xl bg-amber-50 dark:bg-amber-600/10 border border-amber-200 dark:border-amber-600/20 text-xs text-amber-700 dark:text-amber-400">
            Your previous session has expired. Please log in again.
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1.5">
              Email Address
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
                placeholder="faculty@institution.edu"
                className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
              />
            </div>
          </div>

          <div>
            <div className="flex justify-between items-center mb-1.5">
              <label className="text-xs font-semibold text-ink-700 dark:text-sand-300">
                Password
              </label>
              <Link
                to="/forgot-password"
                className="text-xs font-medium text-clay-500 hover:text-clay-600"
              >
                Forgot password?
              </Link>
            </div>
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
                className="w-full pl-9 pr-10 py-2.5 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
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
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white font-semibold text-sm shadow-soft card-lift flex items-center justify-center disabled:opacity-60 transition-all"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Signing in...
              </>
            ) : (
              <>
                Sign In <ArrowRight className="w-4 h-4 ml-1.5" />
              </>
            )}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-sand-200 dark:border-charcoal-700 text-center">
          <p className="text-xs text-ink-500 dark:text-sand-400">
            Don't have an institutional account?{' '}
            <Link to="/register" className="font-semibold text-clay-500 hover:text-clay-600">
              Register here
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};
