import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Generic error boundary that catches thrown errors from children
 * and shows a graceful fallback instead of white-screening.
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack);
    this.props.onError?.(error, info);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          style={{
            padding: 24,
            margin: 8,
            borderRadius: 12,
            background: 'rgba(239,68,68,0.06)',
            border: '1px solid rgba(239,68,68,0.2)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{ fontSize: 18 }}>⚠️</span>
            <span style={{
              fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.1em', color: '#ef4444',
            }}>
              Something went wrong
            </span>
          </div>
          <div style={{
            fontSize: 10, color: 'rgba(255,255,255,0.5)', fontFamily: 'JetBrains Mono, monospace',
            marginBottom: 12, wordBreak: 'break-word', lineHeight: 1.5,
            maxHeight: 120, overflowY: 'auto',
          }}>
            {this.state.error?.message || 'Unknown error'}
          </div>
          <button
            onClick={this.handleRetry}
            style={{
              padding: '6px 16px', borderRadius: 8, border: '1px solid rgba(239,68,68,0.4)',
              background: 'rgba(239,68,68,0.12)', color: '#fca5a5',
              fontSize: 10, fontWeight: 700, cursor: 'pointer',
              textTransform: 'uppercase', letterSpacing: '0.05em',
            }}
          >
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}