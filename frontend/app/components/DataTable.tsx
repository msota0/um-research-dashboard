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

// Constrained to `object` (not `Record<string, unknown>`) so plain interfaces
// like Author/FieldCount satisfy it; cell access casts per-row internally.
export default function DataTable<T extends object>({ columns, rows, onRowClick, emptyMessage }: Props<T>) {
  if (rows.length === 0) {
    return <div className={styles.empty}>{emptyMessage ?? 'No data available.'}</div>;
  }
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key} scope="col">{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={onRowClick ? styles.clickable : ''}
              onClick={() => onRowClick?.(row)}
              {...(onRowClick ? {
                role: 'button',
                tabIndex: 0,
                onKeyDown: (e: React.KeyboardEvent) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick(row); }
                },
              } : {})}
            >
              {columns.map(col => {
                const value = (row as Record<string, unknown>)[col.key];
                return (
                  <td key={col.key}>
                    {col.render ? col.render(value, row) : ((value ?? '—') as React.ReactNode)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
