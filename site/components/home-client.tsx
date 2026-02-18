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
  dailySummaries?: Record<string, DailySummary>;
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

export default function HomeClient({ papers, dates, searchDocs, generatedAt, dailySummary, dailySummaries }: HomeClientProps) {
  const [query, setQuery] = useState('');
  const [dateFilter, setDateFilter] = useState(dates[0] ?? '');
  const [authorFilter, setAuthorFilter] = useState('');
  const [lang, setLang] = useState<'en' | 'zh'>('zh');
  const selectedDate = dateFilter || (dates[0] ?? '');
  const selectedDateIndex = selectedDate ? dates.indexOf(selectedDate) : -1;
  const minDate = dates.length ? dates[dates.length - 1] : undefined;
  const maxDate = dates[0] ?? undefined;

  const canGoPrevDay = selectedDateIndex >= 0 && selectedDateIndex < dates.length - 1;
  const canGoNextDay = selectedDateIndex > 0;

  function goPrevDay() {
    if (!dateFilter) {
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
    if (!dateFilter) {
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
      if (dateFilter && paper.date !== dateFilter) {
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
  const activeDailySummary = useMemo(() => {
    if (!selectedDate) {
      return dailySummary || null;
    }
    if (dailySummaries && dailySummaries[selectedDate]) {
      return dailySummaries[selectedDate];
    }
    if (dailySummary && dailySummary.date === selectedDate) {
      return dailySummary;
    }
    return null;
  }, [dailySummaries, dailySummary, selectedDate]);

  const dateNavControls = (
    <>
      <button
        type="button"
        className="date-nav-btn"
        title="前一天"
        aria-label="前一天"
        onClick={goPrevDay}
        disabled={!!dateFilter && !canGoPrevDay}
      >
        <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">
          <path d="M12.5 5.5L8 10l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>
      <span className="date-nav-current">{dateFilter || '全部（按日期分组）'}</span>
      <button
        type="button"
        className="date-nav-btn"
        title="后一天"
        aria-label="后一天"
        onClick={goNextDay}
        disabled={!!dateFilter && !canGoNextDay}
      >
        <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">
          <path d="M7.5 5.5L12 10l-4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>
    </>
  );

  return (
    <main className="grid home-main">
      <section className="card reveal">
        <div className="controls-grid">
          <label className="filter-field">
            <div className="meta filter-label">关键词</div>
            <div className="calendar-input-wrap">
              <span className="calendar-input-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="14" height="14">
                  <path
                    d="m15.8 15.8 4 4M10.6 16.4a5.8 5.8 0 1 1 0-11.6 5.8 5.8 0 0 1 0 11.6Z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
              <input
                className="input input-with-icon"
                placeholder="title / author / summary"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
          </label>
          <label className="filter-field">
            <div className="meta filter-label">日期</div>
            <div className="calendar-picker-row">
              <div className="calendar-input-wrap">
                <span className="calendar-input-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="14" height="14">
                    <path
                      d="M7.5 3.8v2.1M16.5 3.8v2.1M4.6 8h14.8M6.5 5.9h11c1.1 0 2 .9 2 2v10.2c0 1.1-.9 2-2 2h-11c-1.1 0-2-.9-2-2V7.9c0-1.1.9-2 2-2Z"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.7"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <input
                  type="date"
                  className="input input-calendar"
                  value={dateFilter}
                  min={minDate}
                  max={maxDate}
                  onChange={(e) => setDateFilter(e.target.value)}
                />
              </div>
              <button
                type="button"
                className={`button button-calendar-reset ${dateFilter ? '' : 'active'}`}
                onClick={() => setDateFilter('')}
              >
                全部
              </button>
            </div>
          </label>
          <label className="filter-field">
            <div className="meta filter-label">作者筛选</div>
            <div className="calendar-input-wrap">
              <span className="calendar-input-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="14" height="14">
                  <path
                    d="M12 12.2a3.6 3.6 0 1 0 0-7.2 3.6 3.6 0 0 0 0 7.2Zm-6.2 6.3a6.2 6.2 0 0 1 12.4 0"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
              <input
                className="input input-with-icon"
                placeholder="作者名包含..."
                value={authorFilter}
                onChange={(e) => setAuthorFilter(e.target.value)}
              />
            </div>
          </label>
          <div className="filter-field filter-lang">
            <div className="meta filter-label">
              摘要语言
            </div>
            <div className="summary-lang-tabs">
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

      <DailySummaryPanel summary={activeDailySummary} />

      {visibleDates.map((date, groupIndex) => (
        <section key={date} className="grid date-group">
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
              <p className="meta paper-authors-line">
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
