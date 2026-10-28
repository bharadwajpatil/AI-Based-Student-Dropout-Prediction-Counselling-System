import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { useToast } from '../../context/ToastContext';
import { MailCheck, CheckCircle2, Loader2, ArrowRight } from 'lucide-react';

export const VerifyEmailPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { success, error } = useToast();

  const tokenParam = searchParams.get('token');
  const emailParam = searchParams.get('email');

  const [code, setCode] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [verified, setVerified] = useState<boolean>(false);

  const handleVerify = useCallback(async (tokenVal?: string, codeVal?: string) => {
    setLoading(true);
    try {
      await authApi.verifyEmail({
        token: tokenVal,
        code: codeVal,
        email: emailParam || undefined,
      });
      setVerified(true);
      success('Email Verified', 'Your institutional account is activated.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Verification failed';
      error('Verification Failed', msg);
    } finally {
      setLoading(false);
    }
  }, [emailParam, error, success]);

  // If token is in query param, verify automatically
  useEffect(() => {
    if (tokenParam) {
      handleVerify(tokenParam);
    }
  }, [tokenParam, handleVerify]);

  const handleSubmitCode = (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    handleVerify(undefined, code.trim());
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-cream-50 dark:bg-charcoal-900">
      <div className="w-full max-w-md bg-white dark:bg-charcoal-850 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-8 shadow-lift animate-fade-up text-center">
        <div className="inline-flex w-14 h-14 rounded-2xl bg-cream-100 dark:bg-charcoal-750 text-clay-500 items-center justify-center shadow-soft mb-4">
          {verified ? (
            <CheckCircle2 className="w-8 h-8 text-sage-600" />
          ) : (
            <MailCheck className="w-8 h-8" />
          )}
        </div>

        <h2 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100">
          {verified ? 'Email Verified Successfully!' : 'Verify Your Email'}
        </h2>
        <p className="text-xs text-ink-500 dark:text-sand-400 mt-2 max-w-xs mx-auto">
          {verified
            ? 'Your account is ready. You can now log into the early warning platform.'
            : emailParam
            ? `We sent verification instructions to ${emailParam}. Enter the 6-digit code or click the email link.`
            : 'Enter the verification code sent to your institutional email.'}
        </p>

        {verified ? (
          <div className="mt-8">
            <button
              onClick={() => navigate('/login')}
              className="w-full py-2.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white font-semibold text-sm shadow-soft card-lift flex items-center justify-center transition-all"
            >
              Proceed to Sign In <ArrowRight className="w-4 h-4 ml-1.5" />
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmitCode} className="mt-6 space-y-4 text-left">
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-1">
                6-Digit Verification Code
              </label>
              <input
                type="text"
                required
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="123456"
                className="w-full text-center tracking-widest text-lg font-mono font-bold py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
              />
            </div>

            <button
              type="submit"
              disabled={loading || code.length < 6}
              className="w-full py-2.5 rounded-xl bg-clay-500 hover:bg-clay-600 text-white font-semibold text-sm shadow-soft card-lift flex items-center justify-center disabled:opacity-60 transition-all"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Verifying...
                </>
              ) : (
                'Confirm Code'
              )}
            </button>

            <div className="text-center pt-2">
              <Link to="/login" className="text-xs font-medium text-clay-500 hover:text-clay-600">
                Back to Sign In
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
