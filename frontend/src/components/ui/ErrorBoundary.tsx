import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-[#f0f4ff] dark:bg-[#060d1f] p-8">
          <div className="max-w-md w-full bg-white dark:bg-dark-surface border border-danger-200 dark:border-danger-500/30 rounded-card shadow-card dark:shadow-card-dark p-6 space-y-3">
            <h1 className="text-lg font-bold text-danger-700 dark:text-red-400">
              Something went wrong
            </h1>
            <p className="text-sm text-neutral-600 dark:text-slate-400">
              The app encountered an unexpected error. Try refreshing the page.
            </p>
            <pre className="text-xs text-neutral-500 dark:text-slate-500 bg-neutral-50 dark:bg-[#0a1628] rounded p-3 overflow-auto max-h-40">
              {this.state.error.message}
            </pre>
            <button
              onClick={() => window.location.reload()}
              className="w-full py-2 text-sm font-medium text-white bg-primary-600 dark:bg-primary-500 rounded-lg hover:bg-primary-700 dark:hover:bg-primary-600 transition-colors"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
