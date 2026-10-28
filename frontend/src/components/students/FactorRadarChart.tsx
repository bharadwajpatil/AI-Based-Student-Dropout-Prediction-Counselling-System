import React from 'react';
import type { RiskFactor } from '../../types';

interface FactorBreakdownProps {
  factors: RiskFactor[];
}

export const FactorBreakdown: React.FC<FactorBreakdownProps> = ({ factors }) => {
  if (!factors || factors.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-ink-500 dark:text-sand-400">
        No factor data available for this evaluation.
      </div>
    );
  }

  const getBarColor = (risk: number) => {
    if (risk >= 70) return 'bg-rose-500';
    if (risk >= 40) return 'bg-amber-500';
    return 'bg-sage-500';
  };

  return (
    <div className="space-y-4">
      {factors.map((factor) => {
        const factorPercent = Math.min(Math.round(factor.risk), 100);
        return (
          <div key={factor.name} className="space-y-1.5">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-ink-900 dark:text-sand-100 capitalize">
                {factor.name}
                <span className="ml-2 font-normal text-ink-500 dark:text-sand-400">
                  (weight: {Math.round(factor.weight * 100)}%)
                </span>
              </span>
              <span className="font-semibold text-ink-900 dark:text-sand-100">
                {factor.risk.toFixed(1)} / 100
              </span>
            </div>

            {/* Factor Bar */}
            <div className="w-full bg-sand-200 dark:bg-charcoal-700 rounded-full h-2 overflow-hidden">
              <div
                className={`h-2 rounded-full transition-all duration-500 ${getBarColor(factor.risk)}`}
                style={{ width: `${factorPercent}%` }}
              />
            </div>

            <p className="text-[11px] text-ink-500 dark:text-sand-400 leading-tight">
              {factor.explanation}
            </p>
          </div>
        );
      })}
    </div>
  );
};
