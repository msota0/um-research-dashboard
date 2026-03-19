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
}

export default function BarChart({ labels, datasets, yFormatter, showLegend }: Props) {
  return (
    <Bar
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
