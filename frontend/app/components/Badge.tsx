import styles from './Badge.module.css';

type Source = 'openalex' | 'dimensions' | 'both';

export default function Badge({ source }: { source: Source }) {
  return (
    <span className={`${styles.badge} ${styles[source]}`}>
      {source === 'openalex' ? 'OpenAlex' : source === 'dimensions' ? 'Dimensions AI' : 'Both'}
    </span>
  );
}
