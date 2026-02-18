import HomeClient from '../components/home-client';
import { loadIndexData, loadSearchDocs } from '../lib/data';

export default async function HomePage() {
  const [index, searchDocs] = await Promise.all([loadIndexData(), loadSearchDocs()]);

  return (
    <HomeClient
      papers={index.papers}
      dates={index.dates}
      searchDocs={searchDocs}
      generatedAt={index.generated_at}
      dailySummary={index.daily_summary}
      dailySummaries={index.daily_summaries || {}}
    />
  );
}
