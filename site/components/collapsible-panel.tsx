'use client';

import { useId, useState } from 'react';
import type { ReactNode } from 'react';

interface CollapsiblePanelProps {
  title: ReactNode;
  defaultOpen?: boolean;
  containerClassName?: string;
  toggleClassName?: string;
  arrowClassName?: string;
  contentClassName?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export default function CollapsiblePanel({
  title,
  defaultOpen = false,
  containerClassName,
  toggleClassName,
  arrowClassName,
  contentClassName,
  children,
  footer
}: CollapsiblePanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  const contentId = useId();

  return (
    <section className={containerClassName}>
      <button
        type="button"
        className={toggleClassName}
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen((v) => !v)}
      >
        {title}
        <span className={`${arrowClassName} ${open ? 'open' : ''}`.trim()} aria-hidden="true">
          <svg viewBox="0 0 20 20" width="14" height="14">
            <path d="M5.5 7.5L10 12l4.5-4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </span>
      </button>
      {open ? (
        <div id={contentId} className={contentClassName}>
          {children}
        </div>
      ) : null}
      {footer}
    </section>
  );
}
