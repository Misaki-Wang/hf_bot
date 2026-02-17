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
    <main className="grid" style={{ gap: '1rem' }}>
      <Link href="/">← 返回列表</Link>
      <article className="card paper-detail reveal">
        <h2 className="paper-title" style={{ marginBottom: 0 }}>
          {paper.title || paper.paper_id}
        </h2>
        <div className="meta-row">
          <p className="meta" style={{ margin: 0 }}>
            Date: {paper.date} | Fetched: {paper.fetched_at}
          </p>
        </div>
        <p style={{ margin: 0 }}>
          <strong>Authors:</strong> {paper.authors.length ? paper.authors.join(', ') : 'N/A'}
        </p>

        <div className="link-row">
          <strong>Links:</strong>
          <div className="link-upvote-row">
            <PaperLinks paper={paper} />
            <UpvoteBadge count={paper.upvotes || 0} dense />
          </div>
        </div>

        <AbstractCollapse abstract={paper.abstract} />
        <SummarySwitch summaryEn={paper.summary_en} summaryZh={paper.summary_zh} />
      </article>
    </main>
  );
}
