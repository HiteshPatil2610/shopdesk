import { formatINR } from '@shopdesk/shared';
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  Tooltip,
  type ChartOptions,
} from 'chart.js';
import { useMemo } from 'react';
import { Bar } from 'react-chartjs-2';

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip);

type Props = {
  title: string;
  labels: string[];
  /** Money values as API strings ("990.00"). */
  values: string[];
  horizontal?: boolean;
  /** Extra tooltip lines per bar (e.g. "3 orders"). */
  details?: string[];
  height?: number;
};

function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/**
 * Single-series bar chart (dataviz rules): one validated hue, thin bars with 4px rounded ends,
 * recessive grid, hover tooltip with ₹ values, and a data table for screen readers.
 * Chart.js needs numbers for bar geometry only; labels and tooltips use the exact API strings.
 */
export function BarChart({ title, labels, values, horizontal, details, height = 240 }: Props) {
  const colors = useMemo(
    () => ({
      bar: cssVar('--color-chart-1', '#2a78d6'),
      grid: cssVar('--color-chart-grid', '#e2e8f0'),
      text: cssVar('--color-text-muted', '#64748b'),
    }),
    [],
  );

  const data = {
    labels,
    datasets: [
      {
        label: title,
        data: values.map(Number), // geometry only
        backgroundColor: colors.bar,
        borderRadius: 4,
        borderSkipped: 'start' as const,
        maxBarThickness: horizontal ? 22 : 28,
        categoryPercentage: 0.7,
        barPercentage: 0.9,
      },
    ],
  };

  const valueAxis = {
    beginAtZero: true,
    grid: { color: colors.grid },
    border: { display: false },
    ticks: {
      color: colors.text,
      maxTicksLimit: 5,
      callback: (v: string | number) => `₹${Number(v).toLocaleString('en-IN')}`,
    },
  };
  const categoryAxis = {
    grid: { display: false },
    border: { color: colors.grid },
    ticks: { color: colors.text, autoSkip: true, maxRotation: 0 },
  };

  const options: ChartOptions<'bar'> = {
    indexAxis: horizontal ? 'y' : 'x',
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false }, // single series: the title names it
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const money = values[ctx.dataIndex] ?? '0';
            const extra = details?.[ctx.dataIndex];
            return extra ? `${formatINR(money)} · ${extra}` : formatINR(money);
          },
        },
      },
    },
    scales: horizontal ? { x: valueAxis, y: categoryAxis } : { x: categoryAxis, y: valueAxis },
  };

  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="text-sm font-semibold">{title}</figcaption>
      <div style={{ height }} role="img" aria-label={`${title}. Data table below.`}>
        <Bar data={data} options={options} />
      </div>
      <details className="text-xs text-text-muted">
        <summary className="cursor-pointer">Show as table</summary>
        <table className="mt-2 w-full">
          <tbody>
            {labels.map((label, i) => (
              <tr key={label} className="border-t border-border">
                <th scope="row" className="py-1 text-left font-normal">
                  {label}
                </th>
                <td className="py-1 text-right tabular-nums">{formatINR(values[i] ?? '0')}</td>
                {details && <td className="py-1 pl-3 text-right">{details[i]}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
