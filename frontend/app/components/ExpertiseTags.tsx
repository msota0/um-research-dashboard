'use client';
import styles from './ExpertiseTags.module.css';

export interface ExpertiseKeyword {
  keyword: string;
  total_score: number;
  sources: string[];
  type: string;
}

interface Props {
  keywords: ExpertiseKeyword[];
  maxVisible?: number;
}

const SOURCE_LABELS: Record<string, string> = {
  openalex_topics:   'OA Topic',
  openalex_concepts: 'OA Concept',
  openalex_works:    'OA Works',
  orcid:             'ORCID',
};

const TYPE_CLASS: Record<string, string> = {
  topic:         'typeTopic',
  concept:       'typeConcept',
  extracted:     'typeExtracted',
  self_reported: 'typeSelfReported',
};

function sourceTooltip(sources: string[]): string {
  return sources.map(s => SOURCE_LABELS[s] ?? s).join(' + ');
}

export default function ExpertiseTags({ keywords, maxVisible = 30 }: Props) {
  if (!keywords || keywords.length === 0) {
    return <p className={styles.empty}>No expertise keywords found.</p>;
  }

  const visible = keywords.slice(0, maxVisible);
  const maxScore = visible[0]?.total_score ?? 1;

  return (
    <div className={styles.root}>
      <div className={styles.legend}>
        <span className={`${styles.dot} ${styles.dotTopic}`} />Topic
        <span className={`${styles.dot} ${styles.dotConcept}`} />Concept
        <span className={`${styles.dot} ${styles.dotExtracted}`} />From works
        <span className={`${styles.dot} ${styles.dotSelfReported}`} />Self-reported (ORCID)
      </div>

      <div className={styles.cloud}>
        {visible.map((kw, i) => {
          const sizeRatio = kw.total_score / maxScore;   // 0 → 1
          const fontSize  = 0.72 + sizeRatio * 0.52;    // 0.72rem → 1.24rem
          const opacity   = 0.55 + sizeRatio * 0.45;    // 0.55 → 1.0
          const typeClass = TYPE_CLASS[kw.type] ?? 'typeExtracted';

          return (
            <span
              key={i}
              className={`${styles.tag} ${styles[typeClass]}`}
              style={{ fontSize: `${fontSize}rem`, opacity }}
              title={`Score: ${kw.total_score.toFixed(2)}  |  Sources: ${sourceTooltip(kw.sources)}`}
            >
              {kw.keyword}
            </span>
          );
        })}
      </div>

      <div className={styles.sourceLegend}>
        <span className={styles.sourceNote}>
          Sources: {[...new Set(keywords.flatMap(k => k.sources))].map(s => SOURCE_LABELS[s] ?? s).join(', ')}
        </span>
      </div>
    </div>
  );
}
