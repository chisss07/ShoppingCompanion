import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, LogIn, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { authApi } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { Logo } from '../components/ui/Logo';
import { Button } from '../components/ui/Button';

// ─────────────────────────────────────────────
// LoginPage
// ─────────────────────────────────────────────

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuthStore();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!username.trim() || !password) return;

    setLoading(true);
    setError(null);

    try {
      const { access_token } = await authApi.login(username.trim(), password);
      login(access_token);
      void navigate('/settings');
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Login failed. Please try again.';
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
            Sign in to your account
          </h1>
          <p className="text-sm text-neutral-500 dark:text-slate-400 mt-1">
            Enter your credentials to continue
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
              placeholder="Enter your username"
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
                autoComplete="current-password"
                required
                placeholder="Enter your password"
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

          {/* Submit */}
          <Button
            type="submit"
            variant="primary"
            size="lg"
            fullWidth
            loading={loading}
            leftIcon={<LogIn className="h-4 w-4" />}
          >
            Sign In
          </Button>
        </form>

        {/* Footer link */}
        <p className="mt-6 text-center text-sm text-neutral-500 dark:text-slate-400">
          First time?{' '}
          <Link
            to="/setup"
            className="text-primary-600 dark:text-primary-400 font-medium hover:underline"
          >
            Set up your account
          </Link>
        </p>
      </div>
    </div>
  );
}
