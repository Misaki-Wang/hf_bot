import { cp, mkdir, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const siteRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(siteRoot, '..');

const src = path.join(repoRoot, 'data');
const dest = path.join(siteRoot, 'public', 'data');

async function main() {
  await mkdir(path.join(siteRoot, 'public'), { recursive: true });
  await rm(dest, { recursive: true, force: true });
  await cp(src, dest, { recursive: true });
  console.log(`Synced data: ${src} -> ${dest}`);
}

main().catch((error) => {
  console.error('sync-data failed:', error);
  process.exit(1);
});
