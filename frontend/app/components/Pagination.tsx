import styles from './Pagination.module.css';

interface Props {
  page: number;
  total: number;
  perPage: number;
  onPrev: () => void;
  onNext: () => void;
}

export default function Pagination({ page, total, perPage, onPrev, onNext }: Props) {
  const start = Math.min((page - 1) * perPage + 1, total);
  const end = Math.min(page * perPage, total);
  const totalPages = Math.ceil(total / perPage);
  return (
    <div className={styles.row}>
      <span className={styles.info}>Showing {start}–{end} of {total.toLocaleString()}</span>
      <div className={styles.buttons}>
        <button className={styles.btn} onClick={onPrev} disabled={page <= 1}>← Prev</button>
        <button className={styles.btn} onClick={onNext} disabled={page >= totalPages}>Next →</button>
      </div>
    </div>
  );
}
