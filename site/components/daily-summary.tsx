'use client';

import type { DailySummary } from '../lib/types';
import CollapsiblePanel from './collapsible-panel';

interface DailySummaryPanelProps {
  summary: DailySummary | null | undefined;
}

interface SummaryBlock {
  heading: string;
  kind: 'ul' | 'ol' | 'text';
  items: string[];
}

function parseSummaryBlocks(content: string): SummaryBlock[] {
  const chunks = content
    .split(/\n\s*\n/g)
    .map((chunk) => chunk.split('\n').map((line) => line.trim()).filter(Boolean))
    .filter((lines) => lines.length > 0);

  const blocks: SummaryBlock[] = [];
  for (const lines of chunks) {
    const heading = lines[0] ?? '';
    const body = lines.slice(1);
    if (!body.length) {
      blocks.push({ heading, kind: 'text', items: [] });
      continue;
    }
    if (body.every((line) => /^-\s+/.test(line))) {
      blocks.push({
        heading,
        kind: 'ul',
        items: body.map((line) => line.replace(/^-\s+/, '').trim())
      });
      continue;
    }
    if (body.every((line) => /^\d+\.\s+/.test(line))) {
      blocks.push({
        heading,
        kind: 'ol',
        items: body.map((line) => line.replace(/^\d+\.\s+/, '').trim())
      });
      continue;
    }
    blocks.push({ heading, kind: 'text', items: body });
  }
  return blocks;
}

export default function DailySummaryPanel({ summary }: DailySummaryPanelProps) {
  const content = (summary?.content || '').trim();
  const blocks = parseSummaryBlocks(content);

  if (!content) {
    return null;
  }

  return (
    <CollapsiblePanel
      title={<span className="panel-title panel-title--overview">Overview</span>}
      defaultOpen
      containerClassName="card daily-summary-card"
      toggleClassName="panel-toggle"
      arrowClassName="panel-arrow"
      contentClassName="panel-content daily-summary-content"
      footer={
        <p className="meta daily-summary-meta">
          Date: {summary?.date || '-'} | Source: {summary?.model || summary?.source || '-'}
        </p>
      }
    >
      {blocks.map((block, idx) => (
        <section key={`${block.heading}-${idx}`} className="daily-summary-section">
          {block.heading ? <h4 className="daily-summary-section-title">{block.heading}</h4> : null}
          {block.kind === 'ul' ? (
            <ul className="daily-summary-list">
              {block.items.map((item, itemIdx) => (
                <li key={itemIdx}>{item}</li>
              ))}
            </ul>
          ) : null}
          {block.kind === 'ol' ? (
            <ol className="daily-summary-list daily-summary-list-ordered">
              {block.items.map((item, itemIdx) => (
                <li key={itemIdx}>{item}</li>
              ))}
            </ol>
          ) : null}
          {block.kind === 'text' ? (
            <div className="daily-summary-text-group">
              {block.items.map((item, itemIdx) => (
                <p key={itemIdx}>{item}</p>
              ))}
            </div>
          ) : null}
        </section>
      ))}
    </CollapsiblePanel>
  );
}
