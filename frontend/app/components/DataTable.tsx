'use client';
import styles from './DataTable.module.css';

export interface Column<T = Record<string, unknown>> {
  key: string;
  label: string;
  render?: (value: unknown, row: T) => React.ReactNode;
}

interface Props<T = Record<string, unknown>> {
  columns: Column<T>[];
  rows: T[];
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export default function DataTable<T extends Record<string, unknown>>({ columns, rows, onRowClick, emptyMessage }: Props<T>) {
  if (rows.length === 0) {
    return <div className={styles.empty}>{emptyMessage ?? 'No data available.'}</div>;
  }
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={onRowClick ? styles.clickable : ''}
              onClick={() => onRowClick?.(row)}
            >
              {columns.map(col => (
                <td key={col.key}>
                  {col.render
                    ? col.render(row[col.key], row)
                    : (row[col.key] ?? '—') as React.ReactNode}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
