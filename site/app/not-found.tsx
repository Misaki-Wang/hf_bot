import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="card not-found-card">
      <h2>Paper not found</h2>
      <p>该论文不存在或尚未被抓取归档。</p>
      <Link href="/" className="button not-found-back">
        返回首页
      </Link>
    </main>
  );
}
