'use client';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Filler, Tooltip,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip);

interface Props {
  data: Array<{ year: number; count: number }>;
  color?: string;
}

export default function SparklineChart({ data, color = '#CE1126' }: Props) {
  return (
    <Line
      data={{
        labels: data.map(d => d.year),
        datasets: [{
          data: data.map(d => d.count),
          borderColor: color,
          borderWidth: 2,
          fill: true,
          backgroundColor: color + '22',
          tension: 0.4,
          pointRadius: 0,
        }],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: { x: { display: false }, y: { display: false } },
        animation: false,
      }}
    />
  );
}
