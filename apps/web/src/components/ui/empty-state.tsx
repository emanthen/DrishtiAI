interface EmptyStateProps {
  message: string;
  sub?: string;
  action?: React.ReactNode;
}

export function EmptyState({ message, sub, action }: EmptyStateProps) {
  return (
    <div className="rounded-[12px] border border-hairline dark:border-hairline-dark p-8 text-center">
      <p className="text-sm text-ink dark:text-bone">{message}</p>
      {sub && <p className="mt-1 text-xs text-steel">{sub}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
