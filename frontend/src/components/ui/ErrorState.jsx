import { AlertCircle, RefreshCw, Unplug } from 'lucide-react';

export function ErrorState({ error, onRetry, unavailable = false }) {
  return (
    <div className="error-state">
      <div className="error-icon">
        {unavailable ? <Unplug size={20} /> : <AlertCircle size={20} />}
      </div>
      <strong>{unavailable ? 'Endpoint not implemented yet' : 'Could not reach the backend'}</strong>
      <p>
        {unavailable
          ? 'The backend API this view depends on is not connected yet. Once the endpoint is live, data will appear here automatically.'
          : error || 'Check that the FastAPI backend is running (port 8000) and refresh.'}
      </p>
      {onRetry ? (
        <button className="btn btn-outline btn-sm" onClick={onRetry}>
          <RefreshCw size={13} /> Retry
        </button>
      ) : null}
    </div>
  );
}