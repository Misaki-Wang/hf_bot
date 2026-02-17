import { promises as fs } from 'fs';
import path from 'path';
import type { IndexPayload, PaperRecord, SearchDoc } from './types';

const dataDir = path.join(process.cwd(), 'public', 'data');

const EMPTY_INDEX: IndexPayload = {
  generated_at: '',
  count: 0,
  dates: [],
  daily_summary: null,
  papers: []
};

export async function loadIndexData(): Promise<IndexPayload> {
  const indexPath = path.join(dataDir, 'index.json');
  try {
    const raw = await fs.readFile(indexPath, 'utf-8');
    const parsed = JSON.parse(raw) as IndexPayload;
    if (!parsed || !Array.isArray(parsed.papers)) {
      return EMPTY_INDEX;
    }
    return parsed;
  } catch {
    return EMPTY_INDEX;
  }
}

export async function loadSearchDocs(): Promise<SearchDoc[]> {
  const docsPath = path.join(dataDir, 'search_index.json');
  try {
    const raw = await fs.readFile(docsPath, 'utf-8');
    const parsed = JSON.parse(raw) as SearchDoc[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function getPaperById(id: string): Promise<PaperRecord | null> {
  const index = await loadIndexData();
  return index.papers.find((paper) => paper.paper_id === id) ?? null;
}
