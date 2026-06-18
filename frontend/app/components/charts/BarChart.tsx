'use client';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  PointElement, LineElement, Tooltip, Legend,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Tooltip, Legend);

interface Dataset {
  label: string;
  data: number[];
  color?: string;
  type?: 'bar' | 'line';
}

interface Props {
  labels: (string | number)[];
  datasets: Dataset[];
  yFormatter?: (v: number) => string;
  showLegend?: boolean;
  ariaLabel?: string;
}

function summarize(labels: (string | number)[], datasets: Dataset[]): string {
  if (!labels.length) return 'Chart with no data.';
  const d = datasets[0];
  const top = labels.slice(0, 6).map((l, i) => `${l}: ${d?.data[i] ?? 0}`).join('; ');
  return `${d?.label ?? 'Values'} by category — ${top}${labels.length > 6 ? '; and more.' : '.'}`;
}

export default function BarChart({ labels, datasets, yFormatter, showLegend, ariaLabel }: Props) {
  return (
    <Bar
      role="img"
      aria-label={ariaLabel ?? summarize(labels, datasets)}
      data={{
        labels,
        datasets: datasets.map((ds, i) => ({
          label: ds.label,
          data: ds.data,
          backgroundColor: (ds.color ?? '#CE1126') + (ds.type === 'line' ? '00' : 'CC'),
          borderColor: ds.color ?? '#CE1126',
          borderWidth: ds.type === 'line' ? 2 : 1,
          borderRadius: ds.type === 'line' ? 0 : 4,
          type: ds.type,
          tension: 0.3,
          pointRadius: ds.type === 'line' ? 3 : undefined,
          fill: false,
        })) as never,
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: showLegend ?? false, position: 'top' as const },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 45, font: { size: 11 } } },
          y: {
            beginAtZero: true,
            grid: { color: '#F0F0F0' },
            ticks: { callback: yFormatter ? (v) => yFormatter(Number(v)) : undefined },
          },
        },
      }}
    />
  );
}
