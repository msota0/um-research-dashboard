import Badge from './Badge';
import styles from './ChartCard.module.css';

type Source = 'openalex' | 'dimensions' | 'both';

interface Props {
  title: string;
  source: Source;
  children: React.ReactNode;
  actions?: React.ReactNode;
  tooltip?: string;
  tall?: boolean;
}

export default function ChartCard({ title, source, children, actions, tooltip, tall }: Props) {
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <h3 className={styles.title}>{title}</h3>
          {tooltip && (
            <span className={styles.tooltipIcon} title={tooltip}>ⓘ</span>
          )}
        </div>
        <div className={styles.headerRight}>
          {actions}
          <Badge source={source} />
        </div>
      </div>
      <div className={`${styles.body} ${tall ? styles.tall : ''}`}>
        {children}
      </div>
    </div>
  );
}
