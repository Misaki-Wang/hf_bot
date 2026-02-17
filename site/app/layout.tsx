import type { Metadata } from 'next';
import './globals.css';
import ThemeToggle from '../components/theme-toggle';
import BackToTop from '../components/back-to-top';

export const metadata: Metadata = {
  title: 'HF Papers Archive',
  description: 'Hugging Face Papers daily archive with bilingual summaries'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="container">
          <header className="site-header reveal">
            <div className="site-header-card">
              <div>
                <h1 className="site-title">HF Papers Archive</h1>
                <p className="meta">Carpe diem. Seize the day. Make your lives extraordinary.</p>
              </div>
              <ThemeToggle />
            </div>
          </header>
          {children}
        </div>
        <BackToTop />
      </body>
    </html>
  );
}
