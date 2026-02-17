import type { PaperRecord } from '../lib/types';

interface PaperLinksProps {
  paper: Pick<PaperRecord, 'hf_url' | 'arxiv_url' | 'arxiv_pdf_url' | 'github_url'>;
}

function HfIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
      <path
        d="M7.2 5.3c1.3 0 2.4 1.1 2.4 2.4S8.5 10 7.2 10 4.8 8.9 4.8 7.7s1.1-2.4 2.4-2.4Zm9.6 0c1.3 0 2.4 1.1 2.4 2.4S18.1 10 16.8 10s-2.4-1.1-2.4-2.4 1.1-2.3 2.4-2.3ZM12 10.9c2 0 3.6 1.6 3.6 3.6S14 18.1 12 18.1s-3.6-1.6-3.6-3.6S10 10.9 12 10.9Z"
        fill="currentColor"
      />
    </svg>
  );
}

function ArxivIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
      <path
        d="M6 18.5 10.7 6h2.6L18 18.5h-2.3l-1.1-2.9H9.4l-1.1 2.9H6Zm4.1-4.9h3.8L12 8.9l-1.9 4.7Z"
        fill="currentColor"
      />
    </svg>
  );
}

function PdfIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
      <path
        d="M7.2 4.5h6.9L18.5 9v10.5H7.2V4.5Zm6.1 1.8v3.1h3.1M9.2 14.1h1.6c1.2 0 1.9-.7 1.9-1.8 0-1.1-.7-1.8-1.9-1.8H9.2v3.6Zm.9-2.8h.6c.6 0 1 .3 1 .9s-.4.9-1 .9h-.6v-1.8Zm3.6 2.8h.9v-1.3h1.8v-.9h-1.8v-.9h2v-.9h-2.9v4Zm-4.5 4h1v-2.6h1.2c1.2 0 2-.7 2-1.8 0-1.1-.8-1.8-2-1.8H9.2v6.2Z"
        fill="currentColor"
      />
    </svg>
  );
}

function GithubIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
      <path
        d="M12 .5C5.65.5.5 5.66.5 12.02c0 5.09 3.29 9.4 7.86 10.93.58.1.79-.25.79-.56v-2.15c-3.2.69-3.88-1.36-3.88-1.36-.52-1.33-1.27-1.68-1.27-1.68-1.04-.72.08-.71.08-.71 1.15.08 1.75 1.19 1.75 1.19 1.02 1.76 2.68 1.25 3.33.96.1-.75.4-1.26.73-1.55-2.55-.29-5.23-1.28-5.23-5.7 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.47.11-3.06 0 0 .96-.31 3.14 1.19.91-.25 1.89-.38 2.86-.38s1.95.13 2.86.38c2.18-1.5 3.14-1.19 3.14-1.19.62 1.59.23 2.77.11 3.06.73.81 1.18 1.84 1.18 3.1 0 4.43-2.68 5.41-5.24 5.69.41.35.77 1.04.77 2.09v3.1c0 .31.21.67.8.56a11.52 11.52 0 0 0 7.85-10.93C23.5 5.66 18.35.5 12 .5Z"
        fill="currentColor"
      />
    </svg>
  );
}

export default function PaperLinks({ paper }: PaperLinksProps) {
  return (
    <div className="link-icon-row" aria-label="Paper links">
      <a className="link-icon link-icon--hf" href={paper.hf_url} target="_blank" rel="noreferrer" title="Hugging Face">
        <HfIcon />
        <span>HF</span>
      </a>

      {paper.arxiv_url ? (
        <a
          className="link-icon link-icon--arxiv"
          href={paper.arxiv_url}
          target="_blank"
          rel="noreferrer"
          title="arXiv abstract"
        >
          <ArxivIcon />
          <span>arXiv</span>
        </a>
      ) : null}

      {paper.arxiv_pdf_url ? (
        <a
          className="link-icon link-icon--pdf"
          href={paper.arxiv_pdf_url}
          target="_blank"
          rel="noreferrer"
          title="arXiv PDF"
        >
          <PdfIcon />
          <span>PDF</span>
        </a>
      ) : null}

      {paper.github_url ? (
        <a
          className="link-icon link-icon--github"
          href={paper.github_url}
          target="_blank"
          rel="noreferrer"
          title="GitHub repository"
        >
          <GithubIcon />
          <span>GitHub</span>
        </a>
      ) : null}
    </div>
  );
}
