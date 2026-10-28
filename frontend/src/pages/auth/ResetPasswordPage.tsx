import React, { useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { useToast } from '../../context/ToastContext';
import { Lock, ShieldCheck, Loader2, ArrowRight, Eye, EyeOff } from 'lucide-react';

export const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { success, error } = useToast();

  const tokenParam = searchParams.get('token');

  const [token, setToken] = useState<string>(tokenParam || '');
  const [identifier, setIdentifier] = useState<string>('');
  const [otp, setOtp] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const hasMinLength = password.length >= 10;
  const hasUpperLower = /[a-z]/.test(password) && /[A-Z]/.test(password);
  const hasDigitOrSpecial = /[\d\W]/.test(password);
  const passwordsMatch = password.length > 0 && password === confirmPassword;
  const isValid = hasMinLength && hasUpperLower && hasDigitOrSpecial && passwordsMatch;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;

    setLoading(true);
    try {
      await authApi.resetPassword({
        token: token.trim() ? token.trim() : undefined,
        identifier: identifier.trim() ? identifier.trim() : undefined,
        otp: otp.trim() ? otp.trim() : undefined,
        new_password: password,
      });

      success('Password Updated', 'Your password has been changed. Please log in.');
      navigate('/login');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Reset failed';
      error('Reset Failed', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-cream-50 dark:bg-charcoal-900">
      <div className="w-full max-w-md bg-white dark:bg-charcoal-850 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-8 shadow-lift animate-fade-up">
        <div className="text-center space-y-2 mb-6">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-cream-100 dark:bg-charcoal-750 text-clay-500 items-center justify-center shadow-soft mb-2">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h2 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100">
            Set New Password
          </h2>
          <p className="text-xs text-ink-500 dark:text-sand-400">
            Ensure your new password meets institutional complexity standards
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!tokenParam && (
            <div className="space-y-4 p-3 rounded-xl bg-sand-50 dark:bg-charcoal-750 border border-sand-200 dark:border-charcoal-700">
              <div>
                <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                  Reset Token or Phone Number
                </label>
                <input
                  type="text"
                  value={token || identifier}
                  onChange={(e) => {
                    if (e.target.value.startsWith('+')) {
                      setIdentifier(e.target.value);
                      setToken('');
                    } else {
                      setToken(e.target.value);
                      setIdentifier('');
                    }
                  }}
                  placeholder="Paste URL token or phone number"
                  className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs text-ink-900 dark:text-sand-100"
                />
              </div>

              {identifier && (
                <div>
                  <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                    6-Digit SMS OTP
                  </label>
                  <input
                    type="text"
                    maxLength={6}
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    placeholder="123456"
                    className="w-full px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs text-ink-900 dark:text-sand-100 font-mono tracking-widest text-center"
                  />
                </div>
              )}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              New Password
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

          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
              Confirm New Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-9 pr-10 py-2.5 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-ink-400 hover:text-ink-600 dark:hover:text-sand-200 transition-colors focus:outline-none"
                title={showConfirmPassword ? 'Hide password' : 'Show password'}
              >
                {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Validation Indicators */}
          <div className="grid grid-cols-2 gap-1.5 text-[10px]">
            <div
              className={`p-1.5 rounded text-center font-medium ${
                hasMinLength
                  ? 'bg-sage-100 text-sage-600'
                  : 'bg-sand-200 dark:bg-charcoal-700 text-ink-500'
              }`}
            >
              10+ Characters
            </div>
            <div
              className={`p-1.5 rounded text-center font-medium ${
                hasUpperLower && hasDigitOrSpecial
                  ? 'bg-sage-100 text-sage-600'
                  : 'bg-sand-200 dark:bg-charcoal-700 text-ink-500'
              }`}
            >
              Mixed Case & Digits
            </div>
            <div
              className={`col-span-2 p-1.5 rounded text-center font-medium ${
                passwordsMatch
                  ? 'bg-sage-100 text-sage-600'
                  : 'bg-sand-200 dark:bg-charcoal-700 text-ink-500'
              }`}
            >
              Passwords Match
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !isValid}
            className="w-full mt-2 py-2.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white font-semibold text-sm shadow-soft card-lift flex items-center justify-center disabled:opacity-60 transition-all"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...
              </>
            ) : (
              <>
                Save & Sign In <ArrowRight className="w-4 h-4 ml-1.5" />
              </>
            )}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-sand-200 dark:border-charcoal-700 text-center">
          <Link to="/login" className="text-xs font-medium text-clay-500 hover:text-clay-600">
            Cancel and Return to Login
          </Link>
        </div>
      </div>
    </div>
  );
};
