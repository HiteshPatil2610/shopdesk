import type { HealthResponse } from '../api';
import { Spinner } from './Spinner';

type Props = {
  isLoading: boolean;
  data?: HealthResponse;
  isError: boolean;
};

/** Small status pill: green "API OK", amber "DB error", red "API unreachable". */
export function HealthBadge({ isLoading, data, isError }: Props) {
  if (isLoading) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-bg px-3 py-1 text-sm text-text-muted">
        <Spinner label="Checking API" /> Checking API…
      </span>
    );
  }
  if (isError || !data) {
    return (
      <span className="rounded-full bg-danger/10 px-3 py-1 text-sm font-medium text-danger">
        ✕ API unreachable
      </span>
    );
  }
  if (data.db !== 'ok') {
    return (
      <span className="rounded-full bg-warning/10 px-3 py-1 text-sm font-medium text-warning">
        ⚠ API up, database error
      </span>
    );
  }
  return (
    <span className="rounded-full bg-success/10 px-3 py-1 text-sm font-medium text-success">
      ✓ API OK · {data.app} v{data.version}
    </span>
  );
}
