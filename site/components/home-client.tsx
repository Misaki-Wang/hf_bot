'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import lunr from 'lunr';
import type { DailySummary, PaperRecord, SearchDoc } from '../lib/types';
import PaperLinks from './paper-links';
import AbstractCollapse from './abstract-collapse';
import UpvoteBadge from './upvote-badge';
import DailySummaryPanel from './daily-summary';

interface HomeClientProps {
  papers: PaperRecord[];
  dates: string[];
  searchDocs: SearchDoc[];
  generatedAt: string;
  dailySummary?: DailySummary | null;
}

function normalize(input: string): string {
  return input.trim().toLowerCase();
}

function splitTerms(query: string): string[] {
  return query
    .split(/\s+/)
    .map((term) => term.trim())
    .filter(Boolean);
}

function formatLastUpdated(value: string): string {
  if (!value) {
    return '-';
  }
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
    hour12: false
  }).format(dt);
}

export default function HomeClient({ papers, dates, searchDocs, generatedAt, dailySummary }: HomeClientProps) {
  const [query, setQuery] = useState('');
  const [dateFilter, setDateFilter] = useState('all');
  const [authorFilter, setAuthorFilter] = useState('');
  const [lang, setLang] = useState<'en' | 'zh'>('zh');
  const selectedDate = dateFilter === 'all' ? (dates[0] ?? '') : dateFilter;
  const selectedDateIndex = selectedDate ? dates.indexOf(selectedDate) : -1;

  const canGoPrevDay = selectedDateIndex >= 0 && selectedDateIndex < dates.length - 1;
  const canGoNextDay = selectedDateIndex > 0;

  function goPrevDay() {
    if (dateFilter === 'all') {
      if (dates.length) {
        setDateFilter(dates[0]);
      }
      return;
    }
    if (!canGoPrevDay) {
      return;
    }
    setDateFilter(dates[selectedDateIndex + 1]);
  }

  function goNextDay() {
    if (dateFilter === 'all') {
      if (dates.length) {
        setDateFilter(dates[0]);
      }
      return;
    }
    if (!canGoNextDay) {
      return;
    }
    setDateFilter(dates[selectedDateIndex - 1]);
  }

  const lunrIndex = useMemo(() => {
    if (!searchDocs.length) {
      return null;
    }

    return lunr(function build() {
      this.ref('id');
      this.field('title');
      this.field('authors');
      this.field('abstract');
      this.field('summary_en');
      this.field('summary_zh');

      searchDocs.forEach((doc) => this.add(doc));
    });
  }, [searchDocs]);

  const filtered = useMemo(() => {
    const q = normalize(query);
    const authorQ = normalize(authorFilter);

    let allowedIds: Set<string> | null = null;
    if (q && lunrIndex) {
      try {
        const terms = splitTerms(q);
        if (terms.length) {
          const lunrQuery = terms.map((term) => `${term}*`).join(' ');
          const results = lunrIndex.search(lunrQuery);
          allowedIds = new Set(results.map((item) => item.ref));
        }
      } catch {
        allowedIds = null;
      }
    }

    const matched = papers.filter((paper) => {
      if (dateFilter !== 'all' && paper.date !== dateFilter) {
        return false;
      }

      if (authorQ) {
        const hay = paper.authors.join(' ').toLowerCase();
        if (!hay.includes(authorQ)) {
          return false;
        }
      }

      if (!q) {
        return true;
      }

      if (allowedIds && allowedIds.size > 0) {
        return allowedIds.has(paper.paper_id);
      }

      const fallbackText = [paper.title, paper.authors.join(' '), paper.abstract, paper.summary_en, paper.summary_zh]
        .join(' ')
        .toLowerCase();
      return fallbackText.includes(q);
    });
    matched.sort((a, b) => {
      const byUpvotes = (b.upvotes || 0) - (a.upvotes || 0);
      if (byUpvotes !== 0) {
        return byUpvotes;
      }
      const byDate = b.date.localeCompare(a.date);
      if (byDate !== 0) {
        return byDate;
      }
      return a.paper_id.localeCompare(b.paper_id);
    });
    return matched;
  }, [authorFilter, dateFilter, lunrIndex, papers, query]);

  const grouped = useMemo(() => {
    const groups = new Map<string, PaperRecord[]>();
    for (const paper of filtered) {
      if (!groups.has(paper.date)) {
        groups.set(paper.date, []);
      }
      groups.get(paper.date)!.push(paper);
    }
    return groups;
  }, [filtered]);

  const visibleDates = useMemo(() => {
    return dates.filter((date) => grouped.has(date));
  }, [dates, grouped]);
  const lastUpdated = useMemo(() => formatLastUpdated(generatedAt), [generatedAt]);

  const dateNavControls = (
    <>
      <button
        type="button"
        className="date-nav-btn"
        title="前一天"
        aria-label="前一天"
        onClick={goPrevDay}
        disabled={dateFilter !== 'all' && !canGoPrevDay}
      >
        <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">
          <path d="M12.5 5.5L8 10l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>
      <span className="date-nav-current">{dateFilter === 'all' ? '全部（按日期分组）' : selectedDate}</span>
      <button
        type="button"
        className="date-nav-btn"
        title="后一天"
        aria-label="后一天"
        onClick={goNextDay}
        disabled={dateFilter !== 'all' && !canGoNextDay}
      >
        <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">
          <path d="M7.5 5.5L12 10l-4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>
    </>
  );

  return (
    <main className="grid" style={{ gap: '1.2rem' }}>
      <section className="card reveal">
        <div className="controls-grid">
          <label>
            <div className="meta">关键词</div>
            <input
              className="input"
              placeholder="title / author / summary"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label>
            <div className="meta">日期</div>
            <select className="select" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)}>
              <option value="all">全部</option>
              {dates.map((date) => (
                <option key={date} value={date}>
                  {date}
                </option>
              ))}
            </select>
          </label>
          <label>
            <div className="meta">作者筛选</div>
            <input
              className="input"
              placeholder="作者名包含..."
              value={authorFilter}
              onChange={(e) => setAuthorFilter(e.target.value)}
            />
          </label>
          <div>
            <div className="meta" style={{ marginBottom: '0.28rem' }}>
              摘要语言
            </div>
            <div style={{ display: 'flex', gap: '0.44rem' }}>
              <button className={`button ${lang === 'zh' ? 'active' : ''}`} onClick={() => setLang('zh')}>
                中文
              </button>
              <button className={`button ${lang === 'en' ? 'active' : ''}`} onClick={() => setLang('en')}>
                English
              </button>
            </div>
          </div>
        </div>
        <div className="filters-footer">
          <div className="result-chip">当前结果：{filtered.length} 篇</div>
          <div className="date-nav">{dateNavControls}</div>
        </div>
      </section>

      <DailySummaryPanel summary={dailySummary} />

      {visibleDates.map((date, groupIndex) => (
        <section key={date} className="grid" style={{ gap: '0.72rem' }}>
          <h2 className="date-heading">{date}</h2>
          {grouped.get(date)!.map((paper, idx) => (
            <article
              key={paper.paper_id}
              className="card paper-card reveal"
              style={{ animationDelay: `${Math.min(320, (groupIndex * 70) + (idx * 26))}ms` }}
            >
              <h3 className="paper-title">
                <Link href={`/paper/${encodeURIComponent(paper.paper_id)}`}>{paper.title || paper.paper_id}</Link>
              </h3>
              <p className="meta" style={{ margin: '0 0 0.48rem 0' }}>
                {paper.authors.length ? `Authors: ${paper.authors.join(', ')}` : 'Authors: N/A'}
              </p>
              <div className="link-upvote-row">
                <PaperLinks paper={paper} />
                <UpvoteBadge count={paper.upvotes || 0} dense />
              </div>
              <p className="paper-summary">
                {lang === 'zh' ? paper.summary_zh || '暂无中文摘要' : paper.summary_en || 'No English summary'}
              </p>
              <AbstractCollapse abstract={paper.abstract} />
            </article>
          ))}
        </section>
      ))}

      <section className="card reveal">
        <div className="date-nav date-nav-bottom">{dateNavControls}</div>
      </section>

      <footer className="site-footer">
        <span>© Misaki</span>
        <span className="site-footer-dot" aria-hidden="true">
          ·
        </span>
        <span>Last Updated: {lastUpdated}</span>
      </footer>
    </main>
  );
}
