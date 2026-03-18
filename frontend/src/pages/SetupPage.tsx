import { useState, useEffect, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, UserPlus, AlertCircle, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { authApi } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { Logo } from '../components/ui/Logo';
import { Button } from '../components/ui/Button';

// ─────────────────────────────────────────────
// SetupPage
// ─────────────────────────────────────────────

export default function SetupPage() {
  const navigate = useNavigate();
  const { login, adminExists, setAdminExists } = useAuthStore();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Check if admin already exists — if so, redirect to login
  useEffect(() => {
    async function checkStatus() {
      try {
        const { admin_exists } = await authApi.getStatus();
        setAdminExists(admin_exists);
        if (admin_exists) {
          void navigate('/login');
        }
      } catch {
        // Ignore — backend might not be up yet
      }
    }

    if (adminExists === null) {
      void checkStatus();
    } else if (adminExists) {
      void navigate('/login');
    }
  }, [adminExists, navigate, setAdminExists]);

  const passwordsMatch = password.length > 0 && confirmPassword.length > 0 && password === confirmPassword;
  const passwordMismatch = confirmPassword.length > 0 && password !== confirmPassword;

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!username.trim() || !password || password !== confirmPassword) return;

    setLoading(true);
    setError(null);

    try {
      const { access_token } = await authApi.setup(username.trim(), password);
      login(access_token);
      setAdminExists(true);
      void navigate('/settings');
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Setup failed. Please try again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card animate-fade-in">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <Logo size={40} textClassName="text-xl" />
        </div>

        {/* Heading */}
        <div className="mb-6 text-center">
          <h1 className="text-xl font-bold text-neutral-900 dark:text-slate-100">
            Welcome! Create your admin account
          </h1>
          <p className="text-sm text-neutral-500 dark:text-slate-400 mt-1">
            This will be the only admin account for this instance.
          </p>
        </div>

        {/* Error */}
        {error && (
          <div
            role="alert"
            className={clsx(
              'flex items-start gap-2.5 rounded-lg p-3 mb-5',
              'bg-danger-50 dark:bg-danger-500/10',
              'border border-danger-200 dark:border-danger-500/20',
            )}
          >
            <AlertCircle
              className="h-4 w-4 text-danger-500 flex-shrink-0 mt-0.5"
              aria-hidden="true"
            />
            <p className="text-sm text-danger-700 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {/* Username */}
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-neutral-700 dark:text-slate-300 mb-1.5"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
              placeholder="Choose a username"
              className="input-base"
            />
          </div>

          {/* Password */}
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-neutral-700 dark:text-slate-300 mb-1.5"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
                minLength={8}
                placeholder="At least 8 characters"
                className={clsx('input-base', 'pr-10')}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className={clsx(
                  'absolute right-3 top-1/2 -translate-y-1/2',
                  'text-neutral-400 dark:text-slate-500',
                  'hover:text-neutral-600 dark:hover:text-slate-300',
                  'transition-colors',
                )}
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>

          {/* Confirm password */}
          <div>
            <label
              htmlFor="confirm-password"
              className="block text-sm font-medium text-neutral-700 dark:text-slate-300 mb-1.5"
            >
              Confirm password
            </label>
            <div className="relative">
              <input
                id="confirm-password"
                type={showConfirm ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
                placeholder="Re-enter your password"
                className={clsx(
                  'input-base pr-10',
                  passwordMismatch && 'border-danger-400 dark:border-danger-500 focus:ring-danger-500',
                  passwordsMatch && 'border-success-500 focus:ring-success-500',
                )}
              />
              {/* Match indicator */}
              {passwordsMatch && (
                <CheckCircle
                  className="absolute right-8 top-1/2 -translate-y-1/2 h-4 w-4 text-success-500"
                  aria-hidden="true"
                />
              )}
              <button
                type="button"
                onClick={() => setShowConfirm((v) => !v)}
                aria-label={showConfirm ? 'Hide password' : 'Show password'}
                className={clsx(
                  'absolute right-3 top-1/2 -translate-y-1/2',
                  'text-neutral-400 dark:text-slate-500',
                  'hover:text-neutral-600 dark:hover:text-slate-300',
                  'transition-colors',
                )}
              >
                {showConfirm ? (
                  <EyeOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>
            {passwordMismatch && (
              <p className="mt-1 text-xs text-danger-600 dark:text-red-400">
                Passwords do not match.
              </p>
            )}
          </div>

          {/* Submit */}
          <Button
            type="submit"
            variant="primary"
            size="lg"
            fullWidth
            loading={loading}
            disabled={passwordMismatch || !username || !password || !confirmPassword}
            leftIcon={<UserPlus className="h-4 w-4" />}
          >
            Create Account
          </Button>
        </form>

        {/* Footer link */}
        <p className="mt-6 text-center text-sm text-neutral-500 dark:text-slate-400">
          Already have an account?{' '}
          <Link
            to="/login"
            className="text-primary-600 dark:text-primary-400 font-medium hover:underline"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
