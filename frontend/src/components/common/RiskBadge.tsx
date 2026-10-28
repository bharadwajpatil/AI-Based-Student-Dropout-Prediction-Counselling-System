import React from 'react';
import { ShieldCheck, AlertTriangle, ShieldAlert, HelpCircle } from 'lucide-react';
import type { RiskLevel } from '../../types';

interface RiskBadgeProps {
  level: RiskLevel | string;
  isEscalated?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({
  level,
  isEscalated = false,
  size = 'md',
  className = '',
}) => {
  const getBadgeConfig = (lvl: string) => {
    switch (lvl) {
      case 'Low':
        return {
          bg: 'bg-sage-100 text-sage-600 border-sage-400 dark:bg-sage-600/20 dark:text-sage-400 dark:border-sage-500/30',
          icon: <ShieldCheck className="w-3.5 h-3.5 mr-1 flex-shrink-0" />,
          label: 'Low Risk',
        };
      case 'Medium':
        return {
          bg: 'bg-amber-100 text-amber-600 border-amber-400 dark:bg-amber-600/20 dark:text-amber-400 dark:border-amber-500/30',
          icon: <AlertTriangle className="w-3.5 h-3.5 mr-1 flex-shrink-0" />,
          label: 'Medium Risk',
        };
      case 'High':
        return {
          bg: 'bg-rose-100 text-rose-600 border-rose-400 dark:bg-rose-600/20 dark:text-rose-400 dark:border-rose-500/30',
          icon: <ShieldAlert className="w-3.5 h-3.5 mr-1 flex-shrink-0" />,
          label: 'High Risk',
        };
      default:
        return {
          bg: 'bg-sand-200 text-ink-700 border-sand-300 dark:bg-charcoal-800 dark:text-sand-300 dark:border-sand-400/20',
          icon: <HelpCircle className="w-3.5 h-3.5 mr-1 flex-shrink-0" />,
          label: 'Insufficient Data',
        };
    }
  };

  const config = getBadgeConfig(level);

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 font-medium',
    md: 'text-xs px-2.5 py-1 font-semibold',
    lg: 'text-sm px-3.5 py-1.5 font-semibold',
  }[size];

  const pulseClass = isEscalated && level === 'High' ? 'animate-pulse-subtle ring-2 ring-rose-400/50' : '';

  return (
    <span
      className={`inline-flex items-center rounded-full border shadow-soft ${config.bg} ${sizeClasses} ${pulseClass} ${className}`}
    >
      {config.icon}
      <span>{config.label}</span>
    </span>
  );
};
