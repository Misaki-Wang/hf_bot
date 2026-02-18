'use client';

import { useState } from 'react';

interface SummarySwitchProps {
  summaryEn: string;
  summaryZh: string;
}

export default function SummarySwitch({ summaryEn, summaryZh }: SummarySwitchProps) {
  const [lang, setLang] = useState<'zh' | 'en'>('zh');

  const content = lang === 'zh' ? summaryZh || '暂无中文摘要' : summaryEn || 'No English summary';

  return (
    <section className="summary-switch">
      <div className="summary-switch-tabs">
        <button className={`button ${lang === 'zh' ? 'active' : ''}`} onClick={() => setLang('zh')}>
          中文摘要
        </button>
        <button className={`button ${lang === 'en' ? 'active' : ''}`} onClick={() => setLang('en')}>
          English
        </button>
      </div>
      <p className="paper-summary summary-switch-content">{content}</p>
    </section>
  );
}
