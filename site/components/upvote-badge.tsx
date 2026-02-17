interface UpvoteBadgeProps {
  count: number;
  dense?: boolean;
}

function UpvoteIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path
        d="M9.9 21H5.4c-.9 0-1.6-.7-1.6-1.6v-7.1c0-.9.7-1.6 1.6-1.6h4.5V21Zm2-10.3 2.4-5.4c.2-.5.8-.8 1.3-.6 1.2.3 1.9 1.5 1.6 2.7l-.5 2.4h2.9c1.4 0 2.4 1.3 2 2.6l-1.7 6.1c-.2.9-1 1.5-1.9 1.5H11V10.7Z"
        fill="currentColor"
      />
    </svg>
  );
}

export default function UpvoteBadge({ count, dense = false }: UpvoteBadgeProps) {
  return (
    <span className={`upvote-chip ${dense ? 'dense' : ''}`} title={`Upvotes: ${count}`}>
      <span className="upvote-chip-icon">
        <UpvoteIcon />
      </span>
      <span className="upvote-chip-text">{count}</span>
    </span>
  );
}
