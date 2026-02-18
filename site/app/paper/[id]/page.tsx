import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getPaperById, loadIndexData } from '../../../lib/data';
import SummarySwitch from '../../../components/summary-switch';
import PaperLinks from '../../../components/paper-links';
import AbstractCollapse from '../../../components/abstract-collapse';
import UpvoteBadge from '../../../components/upvote-badge';

interface PaperPageProps {
  params: { id: string };
}

export async function generateStaticParams() {
  const index = await loadIndexData();
  return index.papers.map((paper) => ({ id: paper.paper_id }));
}

export default async function PaperPage({ params }: PaperPageProps) {
  const id = decodeURIComponent(params.id);
  const paper = await getPaperById(id);

  if (!paper) {
    notFound();
  }

  return (
    <main className="grid paper-page">
      <Link href="/" className="paper-back-link">
        <span aria-hidden="true">←</span> 返回列表
      </Link>
      <article className="card paper-detail reveal">
        <div className="paper-detail-header">
          <h2 className="paper-title paper-detail-title">{paper.title || paper.paper_id}</h2>
          <div className="paper-detail-meta">
            <span className="paper-meta-chip">Date: {paper.date}</span>
            <span className="paper-meta-chip">Fetched: {paper.fetched_at}</span>
          </div>
        </div>
        <section className="paper-section">
          <h3 className="paper-section-title">Authors</h3>
          <p className="paper-authors">{paper.authors.length ? paper.authors.join(', ') : 'N/A'}</p>
        </section>

        <section className="paper-section">
          <h3 className="paper-section-title">Links</h3>
          <div className="link-upvote-row link-upvote-row--detail">
            <PaperLinks paper={paper} />
            <UpvoteBadge count={paper.upvotes || 0} dense />
          </div>
        </section>

        <AbstractCollapse abstract={paper.abstract} />
        <SummarySwitch summaryEn={paper.summary_en} summaryZh={paper.summary_zh} />
      </article>
    </main>
  );
}
