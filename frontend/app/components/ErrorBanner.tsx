import styles from './ErrorBanner.module.css';

interface Props {
  message: string;
  critical?: boolean;
}

export default function ErrorBanner({ message, critical }: Props) {
  return (
    <div className={`${styles.banner} ${critical ? styles.critical : ''}`}>
      <span className={styles.icon}>⚠</span>
      {message}
    </div>
  );
}
