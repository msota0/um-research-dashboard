'use client';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip);

interface Props {
  labels: string[];
  data: number[];
  colors?: string[];
  xFormatter?: (v: number) => string;
}

import { CHART_COLORS } from '../../../lib/utils';

export default function HorizontalBarChart({ labels, data, colors, xFormatter }: Props) {
  const bgColors = colors ?? labels.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]);
  return (
    <Bar
      data={{
        labels,
        datasets: [{ data, backgroundColor: bgColors, borderRadius: 3, borderSkipped: false }],
      }}
      options={{
        indexAxis: 'y' as const,
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: '#F0F0F0' },
            ticks: { callback: xFormatter ? (v) => xFormatter(Number(v)) : undefined, font: { size: 11 } },
          },
          y: { grid: { display: false }, ticks: { font: { size: 11 } } },
        },
      }}
    />
  );
}
