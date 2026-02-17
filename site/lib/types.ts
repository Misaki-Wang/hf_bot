export interface PaperRecord {
  date: string;
  paper_id: string;
  title: string;
  authors: string[];
  abstract: string;
  summary_en: string;
  summary_zh: string;
  hf_url: string;
  arxiv_url: string;
  arxiv_pdf_url: string;
  github_url: string;
  upvotes: number;
  fetched_at: string;
}

export interface DailySummary {
  date: string;
  content: string;
  source: string;
  model: string;
  generated_at: string;
}

export interface IndexPayload {
  generated_at: string;
  count: number;
  dates: string[];
  daily_summary?: DailySummary | null;
  papers: PaperRecord[];
}

export interface SearchDoc {
  id: string;
  date: string;
  title: string;
  authors: string;
  abstract: string;
  summary_en: string;
  summary_zh: string;
  upvotes: number;
}
