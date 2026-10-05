type Props = {
  label: string;
  value: string;
  /** Percent change vs yesterday from the server ("12.50", "-3.00"), or null. */
  change?: string | null;
  sub?: string;
  tone?: 'default' | 'warning';
};

/** Stat tile: hero number + "vs yesterday" with an arrow AND sign (never colour alone). */
export function KpiTile({ label, value, change, sub, tone = 'default' }: Props) {
  const up = change != null && !change.startsWith('-');
  const flat = change != null && /^-?0(\.0+)?$/.test(change);
  return (
    <div
      className={`flex flex-col gap-1 rounded-xl border bg-surface p-4 ${
        tone === 'warning' ? 'border-warning/50' : 'border-border'
      }`}
    >
      <p className="text-xs font-semibold tracking-wide text-text-muted uppercase">{label}</p>
      <p className="text-2xl font-bold tabular-nums">{value}</p>
      <p className="text-xs text-text-muted">
        {change != null && (
          <span
            className={`mr-2 font-medium ${flat ? '' : up ? 'text-success' : 'text-danger'}`}
            aria-label={`${up ? 'up' : 'down'} ${change.replace('-', '')} percent vs yesterday`}
          >
            {flat ? '■' : up ? '▲' : '▼'} {up && !flat ? '+' : ''}
            {Number(change).toFixed(1)}%
          </span>
        )}
        {change != null && 'vs yesterday'}
        {change == null && sub}
        {change != null && sub && <span className="block">{sub}</span>}
      </p>
    </div>
  );
}
