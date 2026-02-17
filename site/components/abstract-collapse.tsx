'use client';

import { useState } from 'react';

interface AbstractCollapseProps {
  abstract: string;
}

export default function AbstractCollapse({ abstract }: AbstractCollapseProps) {
  const [open, setOpen] = useState(false);
  const text = (abstract || '').trim();

  if (!text) {
    return (
      <section className="abstract-block">
        <div className="meta">Abstract: N/A</div>
      </section>
    );
  }

  return (
    <section className="abstract-block">
      <button type="button" className="abstract-toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="meta">Abstract</span>
        <span className={`abstract-toggle-arrow ${open ? 'open' : ''}`} aria-hidden="true">
          <svg viewBox="0 0 20 20" width="14" height="14">
            <path d="M5.5 7.5L10 12l4.5-4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </span>
      </button>
      {open ? <p className="paper-summary abstract-text open">{text}</p> : null}
    </section>
  );
}
