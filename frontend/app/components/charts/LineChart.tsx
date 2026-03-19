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
}

export default function LineChart({ labels, datasets, yFormatter, yMax, showLegend }: Props) {
  return (
    <Line
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
