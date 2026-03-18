import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Eye, EyeOff, Save, CheckCircle, AlertCircle, ArrowLeft, LogOut } from 'lucide-react';
import { clsx } from 'clsx';
import { settingsApi } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { Logo } from '../components/ui/Logo';
import { Button } from '../components/ui/Button';
import type { SettingEntry } from '../services/api';

// ─────────────────────────────────────────────
// Key metadata
// ─────────────────────────────────────────────

interface KeyMeta {
  key: string;
  label: string;
  description: string;
  placeholder: string;
}

const KEY_META: KeyMeta[] = [
  {
    key: 'SERPAPI_KEY',
    label: 'SerpAPI Key',
    description: 'Used to search Google Shopping for live product prices.',
    placeholder: 'sk-serp-...',
  },
  {
    key: 'ANTHROPIC_API_KEY',
    label: 'Anthropic API Key',
    description: 'Powers the AI summary and alternative product suggestions.',
    placeholder: 'sk-ant-...',
  },
  {
    key: 'BESTBUY_API_KEY',
    label: 'Best Buy API Key',
    description: 'Fetches direct listings from BestBuy.com.',
    placeholder: 'Your Best Buy developer key',
  },
  {
    key: 'EBAY_APP_ID',
    label: 'eBay App ID',
    description: 'Used to query the eBay Finding API for product listings.',
    placeholder: 'YourApp-...',
  },
  {
    key: 'EBAY_OAUTH_TOKEN',
    label: 'eBay OAuth Token',
    description: 'Required for eBay Browse API access (longer-lived token).',
    placeholder: 'v^1.1#i^1#r^0#p^3#...',
  },
];

// ─────────────────────────────────────────────
// Single key field
// ─────────────────────────────────────────────

interface KeyFieldProps {
  meta: KeyMeta;
  entry: SettingEntry | undefined;
  value: string;
  isDirty: boolean;
  onChange: (key: string, value: string) => void;
}

function KeyField({ meta, entry, value, isDirty, onChange }: KeyFieldProps) {
  const [showValue, setShowValue] = useState(false);

  const displayValue = isDirty ? value : (entry?.masked_value ?? '');
  const isSet = entry?.is_set ?? false;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label
          htmlFor={`key-${meta.key}`}
          className="text-sm font-medium text-neutral-800 dark:text-slate-200"
        >
          {meta.label}
          {isSet && !isDirty && (
            <span className="ml-2 inline-flex items-center gap-1 text-xs text-success-600 dark:text-green-400 font-normal">
              <CheckCircle className="h-3 w-3" aria-hidden="true" />
              Configured
            </span>
          )}
        </label>
      </div>

      <p className="text-xs text-neutral-500 dark:text-slate-400">{meta.description}</p>

      <div className="relative">
        <input
          id={`key-${meta.key}`}
          type={showValue ? 'text' : 'password'}
          value={displayValue}
          onChange={(e) => onChange(meta.key, e.target.value)}
          placeholder={meta.placeholder}
          className={clsx(
            'input-base pr-10',
            isDirty && 'border-primary-400 dark:border-primary-500',
          )}
          aria-describedby={`desc-${meta.key}`}
        />
        <button
          type="button"
          onClick={() => setShowValue((v) => !v)}
          aria-label={showValue ? `Hide ${meta.label}` : `Show ${meta.label}`}
          className={clsx(
            'absolute right-3 top-1/2 -translate-y-1/2',
            'text-neutral-400 dark:text-slate-500',
            'hover:text-neutral-600 dark:hover:text-slate-300',
            'transition-colors',
          )}
        >
          {showValue ? (
            <EyeOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Eye className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>

      {isDirty && (
        <p className="text-xs text-primary-600 dark:text-primary-400">
          Unsaved change — click Save Changes to apply.
        </p>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Toast notification
// ─────────────────────────────────────────────

type ToastType = 'success' | 'error';

interface ToastProps {
  type: ToastType;
  message: string;
}

function Toast({ type, message }: ToastProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={clsx(
        'fixed bottom-6 right-6 z-50',
        'flex items-center gap-2.5 px-4 py-3 rounded-card shadow-card-elevated',
        'animate-slide-down text-sm font-medium',
        type === 'success'
          ? 'bg-success-500 text-white'
          : 'bg-danger-500 text-white',
      )}
    >
      {type === 'success' ? (
        <CheckCircle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
      ) : (
        <AlertCircle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
      )}
      {message}
    </div>
  );
}

// ─────────────────────────────────────────────
// SettingsPage
// ─────────────────────────────────────────────

export default function SettingsPage() {
  const { logout } = useAuthStore();

  const [entries, setEntries] = useState<SettingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastProps | null>(null);

  // Track user edits: key → new value (only keys that have been changed)
  const [edits, setEdits] = useState<Record<string, string>>({});

  const showToast = useCallback((type: ToastType, message: string) => {
    setToast({ type, message });
    const timer = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(timer);
  }, []);

  // Fetch current settings on mount
  useEffect(() => {
    async function fetchSettings() {
      try {
        const data = await settingsApi.getSettings();
        setEntries(data);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load settings.';
        setFetchError(message);
      } finally {
        setLoading(false);
      }
    }
    void fetchSettings();
  }, []);

  const handleChange = (key: string, value: string) => {
    setEdits((prev) => ({ ...prev, [key]: value }));
  };

  const hasDirtyFields = Object.keys(edits).length > 0;

  const handleSave = async () => {
    if (!hasDirtyFields) return;

    // Filter out empty strings — don't overwrite with blank
    const updates: Record<string, string> = {};
    for (const [k, v] of Object.entries(edits)) {
      if (v.trim()) updates[k] = v.trim();
    }

    if (Object.keys(updates).length === 0) {
      showToast('error', 'No non-empty values to save.');
      return;
    }

    setSaving(true);
    try {
      await settingsApi.updateSettings(updates);
      // Re-fetch to get updated masked values
      const refreshed = await settingsApi.getSettings();
      setEntries(refreshed);
      setEdits({});
      showToast('success', `Saved ${Object.keys(updates).length} setting(s) successfully.`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save settings.';
      showToast('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Logo iconOnly size={24} />
            <h1 className="text-xl font-bold text-neutral-900 dark:text-slate-100">
              API Settings
            </h1>
          </div>
          <p className="text-sm text-neutral-500 dark:text-slate-400">
            Configure the API keys used by ShopCompare to fetch prices.
          </p>
        </div>

        <button
          onClick={handleLogout}
          aria-label="Log out"
          className={clsx(
            'flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg',
            'text-neutral-500 dark:text-slate-400',
            'hover:bg-danger-50 dark:hover:bg-danger-500/10',
            'hover:text-danger-600 dark:hover:text-red-400',
            'transition-colors duration-150',
          )}
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Logout
        </button>
      </div>

      {/* Divider */}
      <hr className="border-primary-100 dark:border-dark-border" />

      {/* Loading */}
      {loading && (
        <div className="space-y-5">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="animate-pulse space-y-2">
              <div className="h-4 bg-primary-100 dark:bg-primary-900/40 rounded w-1/3" />
              <div className="h-3 bg-primary-50 dark:bg-primary-900/20 rounded w-2/3" />
              <div className="h-10 bg-primary-50 dark:bg-primary-900/20 rounded" />
            </div>
          ))}
        </div>
      )}

      {/* Fetch error */}
      {!loading && fetchError && (
        <div
          role="alert"
          className={clsx(
            'flex items-start gap-3 rounded-lg p-4',
            'bg-danger-50 dark:bg-danger-500/10',
            'border border-danger-200 dark:border-danger-500/20',
          )}
        >
          <AlertCircle
            className="h-5 w-5 text-danger-500 flex-shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <p className="text-sm text-danger-700 dark:text-red-400">{fetchError}</p>
        </div>
      )}

      {/* Key fields */}
      {!loading && !fetchError && (
        <div
          className={clsx(
            'rounded-card',
            'bg-white dark:bg-dark-surface',
            'border border-primary-100 dark:border-dark-border',
            'shadow-card dark:shadow-card-dark',
            'divide-y divide-primary-50 dark:divide-dark-border',
          )}
        >
          {KEY_META.map((meta) => {
            const entry = entries.find((e) => e.key === meta.key);
            const isDirty = meta.key in edits;
            const currentValue = edits[meta.key] ?? '';

            return (
              <div key={meta.key} className="p-5">
                <KeyField
                  meta={meta}
                  entry={entry}
                  value={currentValue}
                  isDirty={isDirty}
                  onChange={handleChange}
                />
              </div>
            );
          })}
        </div>
      )}

      {/* Save button row */}
      {!loading && !fetchError && (
        <div className="flex items-center justify-between gap-4">
          <Link
            to="/"
            className={clsx(
              'flex items-center gap-1.5 text-sm font-medium',
              'text-neutral-500 dark:text-slate-400',
              'hover:text-primary-600 dark:hover:text-primary-400',
              'transition-colors',
            )}
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            Back to Search
          </Link>

          <Button
            variant="primary"
            size="md"
            loading={saving}
            disabled={!hasDirtyFields}
            leftIcon={<Save className="h-4 w-4" />}
            onClick={() => void handleSave()}
          >
            Save Changes
          </Button>
        </div>
      )}

      {/* Toast */}
      {toast && <Toast type={toast.type} message={toast.message} />}
    </div>
  );
}
