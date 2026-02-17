import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="card">
      <h2>Paper not found</h2>
      <p>该论文不存在或尚未被抓取归档。</p>
      <Link href="/">返回首页</Link>
    </main>
  );
}
