interface PageHeaderProps {
  title: string;
  description?: string;
  right?: React.ReactNode;
}

export function PageHeader({ title, description, right }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <h1 className="text-lg font-medium text-ink dark:text-bone">{title}</h1>
        {description && <p className="text-xs text-steel mt-0.5">{description}</p>}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}
