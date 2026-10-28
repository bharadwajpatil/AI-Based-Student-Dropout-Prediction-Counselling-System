import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { useToast } from '../../context/ToastContext';
import { KeyRound, Mail, Phone, Loader2, ArrowLeft } from 'lucide-react';

export const ForgotPasswordPage: React.FC = () => {
  const { success, error } = useToast();
  const [identifier, setIdentifier] = useState<string>('');
  const [channel, setChannel] = useState<'email' | 'sms'>('email');
  const [loading, setLoading] = useState<boolean>(false);
  const [submitted, setSubmitted] = useState<boolean>(false);
  const [countdown, setCountdown] = useState<number>(0);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;
    if (countdown > 0) {
      timer = setInterval(() => setCountdown((c) => c - 1), 1000);
    }
    return () => clearInterval(timer);
  }, [countdown]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (countdown > 0) return;

    setLoading(true);
    try {
      await authApi.forgotPassword({ identifier, channel });
      setSubmitted(true);
      setCountdown(60);
      success(
        'Request Sent',
        'If an account exists, instructions have been dispatched.'
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Request failed';
      error('Error', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-cream-50 dark:bg-charcoal-900">
      <div className="w-full max-w-md bg-white dark:bg-charcoal-850 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-8 shadow-lift animate-fade-up">
        <div className="text-center space-y-2 mb-6">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-cream-100 dark:bg-charcoal-750 text-clay-500 items-center justify-center shadow-soft mb-2">
            <KeyRound className="w-6 h-6" />
          </div>
          <h2 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100">
            Forgot Password
          </h2>
          <p className="text-xs text-ink-500 dark:text-sand-400">
            {channel === 'email'
              ? 'Enter your institutional email to receive reset instructions.'
              : 'Enter your registered phone number to receive an SMS OTP.'}
          </p>
        </div>

        {submitted ? (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-cream-50 dark:bg-charcoal-750 border border-sand-200 dark:border-charcoal-700 text-xs text-ink-700 dark:text-sand-300 leading-relaxed">
              If an account is associated with <strong>{identifier}</strong>, instructions have been sent. Please check your inbox or phone.
            </div>

            <div className="text-center">
              <button
                onClick={handleSubmit}
                disabled={countdown > 0 || loading}
                className="text-xs font-semibold text-clay-500 hover:text-clay-600 disabled:opacity-50"
              >
                {countdown > 0 ? `Resend instructions in ${countdown}s` : 'Resend instructions'}
              </button>
            </div>

            <div className="pt-2 text-center">
              <Link
                to="/reset-password"
                className="inline-block py-2 px-4 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
              >
                Proceed to Reset Password
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                {channel === 'email' ? 'Institutional Email' : 'Phone Number (E.164)'}
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
                  {channel === 'email' ? <Mail className="w-4 h-4" /> : <Phone className="w-4 h-4" />}
                </div>
                <input
                  type={channel === 'email' ? 'email' : 'tel'}
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder={channel === 'email' ? 'user@university.edu' : '+919876543210'}
                  className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-sm text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
                />
              </div>
            </div>

            <div className="text-right">
              <button
                type="button"
                onClick={() => {
                  setChannel(channel === 'email' ? 'sms' : 'email');
                  setIdentifier('');
                }}
                className="text-xs font-semibold text-clay-500 hover:text-clay-600"
              >
                {channel === 'email' ? 'Send SMS OTP instead' : 'Send email link instead'}
              </button>
            </div>

            <button
              type="submit"
              disabled={loading || !identifier}
              className="w-full py-2.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white font-semibold text-sm shadow-soft card-lift flex items-center justify-center disabled:opacity-60 transition-all"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Sending...
                </>
              ) : (
                'Send Reset Instructions'
              )}
            </button>
          </form>
        )}

        <div className="mt-6 pt-4 border-t border-sand-200 dark:border-charcoal-700 text-center">
          <Link
            to="/login"
            className="inline-flex items-center text-xs font-medium text-ink-600 dark:text-sand-400 hover:text-clay-500"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Return to Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};
