'use client';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { CHART_COLORS } from '../../../lib/utils';

ChartJS.register(ArcElement, Tooltip, Legend);

interface Props { labels: string[]; data: number[]; colors?: string[]; }

export default function PieChart({ labels, data, colors }: Props) {
  const bgColors = colors ?? labels.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]);
  const total = data.reduce((a, b) => a + b, 0);
  return (
    <Pie
      data={{ labels, datasets: [{ data, backgroundColor: bgColors, borderWidth: 2, borderColor: '#fff' }] }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right' as const, labels: { font: { size: 11 }, boxWidth: 14 } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const pct = total > 0 ? ((ctx.raw as number / total) * 100).toFixed(1) : 0;
                return ` ${ctx.label}: ${ctx.raw} (${pct}%)`;
              },
            },
          },
        },
      }}
    />
  );
}
