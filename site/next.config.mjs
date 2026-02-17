/** @type {import('next').NextConfig} */
const repositoryName = process.env.GITHUB_REPOSITORY?.split('/')[1] || '';
const isGithubActions = process.env.GITHUB_ACTIONS === 'true';
const configuredBasePath = process.env.NEXT_BASE_PATH;
const basePath = configuredBasePath ?? (isGithubActions && repositoryName ? `/${repositoryName}` : '');

const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
  basePath,
  assetPrefix: basePath || undefined
};

export default nextConfig;
