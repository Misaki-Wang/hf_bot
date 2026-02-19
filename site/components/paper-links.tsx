import type { PaperRecord } from '../lib/types';

interface PaperLinksProps {
  paper: Pick<PaperRecord, 'hf_url' | 'arxiv_url' | 'arxiv_pdf_url' | 'github_url'>;
}

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || '';

function iconSrc(filename: string): string {
  return `${BASE_PATH}/icons/${filename}`.replace(/\/{2,}/g, '/');
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
        <img src={iconSrc('huggingface.svg')} width="15" height="15" alt="" aria-hidden="true" className="brand-icon-svg" />
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
          <img src={iconSrc('arxiv.svg')} width="15" height="15" alt="" aria-hidden="true" className="brand-icon-svg" />
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
          <img src={iconSrc('pdf.svg')} width="15" height="15" alt="" aria-hidden="true" className="brand-icon-svg" />
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
