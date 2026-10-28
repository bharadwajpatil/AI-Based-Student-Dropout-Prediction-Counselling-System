import React from 'react';
import { useKpiCounter } from '../../hooks/useKpiCounter';

interface KpiCardProps {
  title: string;
  value: number;
  subtitle?: string;
  icon: React.ReactNode;
  variant?: 'clay' | 'sage' | 'amber' | 'rose' | 'sand';
  suffix?: string;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  variant = 'clay',
  suffix = '',
}) => {
  const animatedValue = useKpiCounter(value);

  const getVariantStyles = () => {
    switch (variant) {
      case 'sage':
        return {
          iconBg: 'bg-sage-100 text-sage-600 dark:bg-sage-600/20 dark:text-sage-400',
          border: 'border-sage-200 dark:border-sage-600/30',
        };
      case 'amber':
        return {
          iconBg: 'bg-amber-100 text-amber-600 dark:bg-amber-600/20 dark:text-amber-400',
          border: 'border-amber-200 dark:border-amber-600/30',
        };
      case 'rose':
        return {
          iconBg: 'bg-rose-100 text-rose-600 dark:bg-rose-600/20 dark:text-rose-400',
          border: 'border-rose-200 dark:border-rose-600/30',
        };
      case 'sand':
        return {
          iconBg: 'bg-sand-200 text-ink-700 dark:bg-sand-400/20 dark:text-sand-300',
          border: 'border-sand-300 dark:border-sand-400/30',
        };
      case 'clay':
      default:
        return {
          iconBg: 'bg-cream-100 text-clay-500 dark:bg-clay-600/20 dark:text-clay-400',
          border: 'border-sand-200 dark:border-charcoal-800',
        };
    }
  };

  const styles = getVariantStyles();

  return (
    <div
      className={`bg-white dark:bg-charcoal-800 rounded-2xl border ${styles.border} p-6 shadow-soft card-lift`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-ink-500 dark:text-sand-400">
            {title}
          </p>
          <div className="mt-2 flex items-baseline">
            <span className="font-display text-3xl font-bold tracking-tight text-ink-900 dark:text-sand-100">
              {animatedValue.toLocaleString()}
              {suffix}
            </span>
          </div>
          {subtitle && (
            <p className="mt-1 text-xs text-ink-500 dark:text-sand-400">{subtitle}</p>
          )}
        </div>
        <div className={`p-3.5 rounded-xl ${styles.iconBg}`}>{icon}</div>
      </div>
    </div>
  );
};
