'use client';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Filler, Tooltip, Legend,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

interface Dataset {
  label: string;
  data: number[];
  color: string;
  fill?: boolean;
}

interface Props {
  labels: (string | number)[];
  datasets: Dataset[];
  yFormatter?: (v: number) => string;
  yMax?: number;
  showLegend?: boolean;
  ariaLabel?: string;
}

function summarize(labels: (string | number)[], datasets: Dataset[]): string {
  if (!labels.length) return 'Line chart with no data.';
  const d = datasets[0];
  const first = `${labels[0]}: ${d?.data[0] ?? 0}`;
  const last = `${labels[labels.length - 1]}: ${d?.data[d.data.length - 1] ?? 0}`;
  return `Line chart of ${d?.label ?? 'values'} over ${labels.length} points, from ${first} to ${last}.`;
}

export default function LineChart({ labels, datasets, yFormatter, yMax, showLegend, ariaLabel }: Props) {
  return (
    <Line
      role="img"
      aria-label={ariaLabel ?? summarize(labels, datasets)}
      data={{
        labels,
        datasets: datasets.map(ds => ({
          label: ds.label,
          data: ds.data,
          borderColor: ds.color,
          backgroundColor: ds.color + '22',
          fill: ds.fill ?? false,
          tension: 0.35,
          pointBackgroundColor: ds.color,
          pointRadius: 3,
        })),
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: showLegend ?? false, position: 'top' as const } },
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: true,
            ...(yMax ? { max: yMax } : {}),
            grid: { color: '#F0F0F0' },
            ticks: { callback: yFormatter ? (v) => yFormatter(Number(v)) : undefined },
          },
        },
      }}
    />
  );
}
