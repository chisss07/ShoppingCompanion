import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, PauseCircle, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { useSearchStore } from '../../store/searchStore';
import type { SourceStep, SourceStepStatus } from '../../types';

// ─────────────────────────────────────────────
// Step icon
// ─────────────────────────────────────────────

function StepIcon({ status }: { status: SourceStepStatus }) {
  switch (status) {
    case 'complete':
      return <CheckCircle className="h-5 w-5 text-success-500" aria-hidden="true" />;
    case 'error':
      return <XCircle className="h-5 w-5 text-danger-500" aria-hidden="true" />;
    case 'timeout':
      return <PauseCircle className="h-5 w-5 text-warning-500" aria-hidden="true" />;
    case 'active':
      return (
        <span className="relative flex h-5 w-5 items-center justify-center">
          <Loader2
            className="h-5 w-5 animate-spin text-primary-600 dark:text-primary-400"
            aria-hidden="true"
          />
        </span>
      );
    default:
      return (
        <span
          className="h-5 w-5 rounded-full border-2 border-primary-200 dark:border-primary-800 bg-white dark:bg-dark-surface"
          aria-hidden="true"
        />
      );
  }
}

// ─────────────────────────────────────────────
// Single step
// ─────────────────────────────────────────────

function SourceStepItem({ step, isLast }: { step: SourceStep; isLast: boolean }) {
  const isDone =
    step.status === 'complete' || step.status === 'error' || step.status === 'timeout';

  return (
    <li className="flex flex-col items-center gap-1 flex-1 min-w-0">
      <div className="flex w-full items-center">
        {/* Left connector */}
        <div
          className={clsx(
            'flex-1 h-0.5 transition-colors duration-500',
            isDone
              ? 'bg-primary-300 dark:bg-primary-700'
              : 'bg-primary-100 dark:bg-primary-900/60',
          )}
          aria-hidden="true"
        />

        {/* Icon */}
        <StepIcon status={step.status} />

        {/* Right connector — only if not last */}
        {!isLast ? (
          <div
            className={clsx(
              'flex-1 h-0.5 transition-colors duration-500',
              step.status === 'complete'
                ? 'bg-success-500'
                : 'bg-primary-100 dark:bg-primary-900/60',
            )}
            aria-hidden="true"
          />
        ) : (
          <div className="flex-1 bg-transparent" aria-hidden="true" />
        )}
      </div>

      {/* Source name */}
      <span
        className={clsx(
          'text-xs font-medium text-center leading-tight px-0.5 truncate max-w-full',
          step.status === 'active' && 'text-primary-700 dark:text-primary-300',
          step.status === 'complete' && 'text-success-700 dark:text-green-400',
          step.status === 'error' && 'text-danger-600 dark:text-red-400',
          step.status === 'timeout' && 'text-warning-700 dark:text-yellow-400',
          step.status === 'pending' && 'text-neutral-400 dark:text-slate-500',
        )}
      >
        {step.display_name}
      </span>

      {/* Result count */}
      {step.results_count !== undefined && step.results_count > 0 && (
        <span className="text-xs text-neutral-400 dark:text-slate-500">
          {step.results_count} result{step.results_count !== 1 ? 's' : ''}
        </span>
      )}
    </li>
  );
}

// ─────────────────────────────────────────────
// ProgressTracker component
// ─────────────────────────────────────────────

interface ProgressTrackerProps {
  visible: boolean;
}

export function ProgressTracker({ visible }: ProgressTrackerProps) {
  const { sourceSteps, progressPercent, statusText, searchStatus } = useSearchStore();
  const [rendered, setRendered] = useState(false);
  const [animateOut, setAnimateOut] = useState(false);

  // Slide down when search starts
  useEffect(() => {
    if (visible && !rendered) {
      setRendered(true);
      setAnimateOut(false);
    }
  }, [visible, rendered]);

  // Slide up 600ms after complete
  useEffect(() => {
    if (!visible && rendered) {
      const timer = setTimeout(() => {
        setAnimateOut(true);
        const hideTimer = setTimeout(() => setRendered(false), 350);
        return () => clearTimeout(hideTimer);
      }, 600);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [visible, rendered]);

  if (!rendered) return null;

  const isComplete = searchStatus === 'complete';

  return (
    <div
      aria-live="polite"
      aria-label="Search progress"
      className={clsx(
        'overflow-hidden transition-all duration-300',
        animateOut ? 'max-h-0 opacity-0' : 'max-h-64 opacity-100 animate-slide-down',
      )}
    >
      <div
        className={clsx(
          'bg-white dark:bg-dark-surface',
          'border border-primary-100 dark:border-dark-border',
          'rounded-card shadow-card dark:shadow-card-dark',
          'p-4 space-y-4',
        )}
      >
        {/* Progress bar */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-neutral-500 dark:text-slate-400">
            <span>{statusText || 'Searching...'}</span>
            <span className="font-mono tabular-nums font-medium text-primary-700 dark:text-primary-400">
              {progressPercent}%
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-primary-100 dark:bg-primary-900/40">
            <div
              role="progressbar"
              aria-valuenow={progressPercent}
              aria-valuemin={0}
              aria-valuemax={100}
              className={clsx(
                'h-full rounded-full progress-fill',
                isComplete
                  ? 'bg-success-500'
                  : 'bg-primary-600 dark:bg-primary-500',
              )}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Source steps */}
        {sourceSteps.length > 0 && (
          <ul
            className="flex items-start gap-0"
            role="list"
            aria-label="Source progress"
          >
            {sourceSteps.map((step, i) => (
              <SourceStepItem
                key={step.source_id}
                step={step}
                isLast={i === sourceSteps.length - 1}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
