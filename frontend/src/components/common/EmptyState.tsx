import React from 'react';
import { FolderOpen } from 'lucide-react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionText,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-charcoal-800 rounded-2xl border border-dashed border-sand-300 dark:border-charcoal-700">
      <div className="w-16 h-16 rounded-2xl bg-cream-100 dark:bg-charcoal-750 flex items-center justify-center text-clay-500 mb-4 shadow-soft">
        {icon || <FolderOpen className="w-8 h-8" />}
      </div>
      <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-sand-100">
        {title}
      </h3>
      <p className="mt-2 text-sm text-ink-500 dark:text-sand-400 max-w-sm">
        {description}
      </p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="mt-6 px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white font-medium text-sm shadow-soft card-lift transition-all"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
