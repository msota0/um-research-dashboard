import styles from './Skeleton.module.css';

interface Props { height?: number | string; width?: number | string; borderRadius?: number | string; }

export default function Skeleton({ height = 200, width = '100%', borderRadius = 8 }: Props) {
  return (
    <div
      className={styles.skeleton}
      style={{ height, width, borderRadius }}
    />
  );
}
