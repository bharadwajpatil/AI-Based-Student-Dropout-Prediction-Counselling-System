import React, { useState } from 'react';
import { Sparkles, Calendar, RotateCcw, CheckSquare, Square, AlertCircle, Loader2 } from 'lucide-react';
import type { AiRecommendation } from '../../types';

interface AiRecommendationCardProps {
  recommendation: AiRecommendation | null | undefined;
  onRegenerate: (notes?: string) => Promise<void>;
  loading?: boolean;
}

export const AiRecommendationCard: React.FC<AiRecommendationCardProps> = ({
  recommendation,
  onRegenerate,
  loading = false,
}) => {
  const [completedActions, setCompletedActions] = useState<Record<number, boolean>>({});
  const [showNotesInput, setShowNotesInput] = useState<boolean>(false);
  const [notes, setNotes] = useState<string>('');
  const [isRegenerating, setIsRegenerating] = useState<boolean>(false);

  const toggleAction = (idx: number) => {
    setCompletedActions((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const handleRegenerateClick = async () => {
    setIsRegenerating(true);
    try {
      await onRegenerate(notes.trim() ? notes : undefined);
      setShowNotesInput(false);
      setNotes('');
    } finally {
      setIsRegenerating(false);
    }
  };

  if (!recommendation) {
    return (
      <div className="rounded-2xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 p-6 text-center space-y-3">
        <Sparkles className="w-8 h-8 text-clay-500 mx-auto" />
        <h4 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
          No AI Recommendations Generated Yet
        </h4>
        <p className="text-xs text-ink-500 dark:text-sand-400 max-w-sm mx-auto">
          Generate structured, personalized intervention steps based on current academic trajectory and risk factors.
        </p>
        <button
          onClick={() => handleRegenerateClick()}
          disabled={loading || isRegenerating}
          className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
        >
          {loading || isRegenerating ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4 mr-2" />
          )}
          Generate Recommendations
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-sand-200 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 p-6 shadow-soft space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="p-2 rounded-xl bg-cream-100 dark:bg-charcoal-750 text-clay-500">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h4 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
              Personalized Intervention Plan
            </h4>
            <div className="flex items-center space-x-2 mt-0.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-cream-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 border border-sand-200 dark:border-charcoal-600">
                Source: {recommendation.ai_source === 'gemini' ? 'Gemini AI' : 'Deterministic Template'}
              </span>
              {recommendation.is_outdated && (
                <span className="flex items-center text-[10px] text-amber-600 bg-amber-50 dark:bg-amber-600/10 px-2 py-0.5 rounded-full font-medium">
                  <AlertCircle className="w-3 h-3 mr-1" /> Data updated since plan
                </span>
              )}
            </div>
          </div>
        </div>

        <button
          onClick={() => setShowNotesInput(!showNotesInput)}
          className="text-xs font-medium text-clay-500 hover:text-clay-600 flex items-center p-1.5 rounded-lg hover:bg-cream-50 dark:hover:bg-charcoal-750 transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5 mr-1" /> Regenerate
        </button>
      </div>

      {/* Outdated Notice */}
      {recommendation.is_outdated && (
        <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-600/10 border border-amber-200 dark:border-amber-600/20 text-xs text-amber-700 dark:text-amber-400">
          This recommendation was calculated before recent academic modifications. Consider regenerating with current scores.
        </div>
      )}

      {/* Regenerate form with notes */}
      {showNotesInput && (
        <div className="p-4 rounded-xl bg-cream-50 dark:bg-charcoal-750 border border-sand-200 dark:border-charcoal-700 space-y-3 animate-fade-up">
          <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300">
            Observation Notes (Optional context for AI generation)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add faculty observations (e.g. medical leave, family situation, language barrier)..."
            rows={3}
            className="w-full p-2.5 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs text-ink-900 dark:text-sand-100"
          />
          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowNotesInput(false)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-ink-600 dark:text-sand-400"
            >
              Cancel
            </button>
            <button
              onClick={handleRegenerateClick}
              disabled={isRegenerating}
              className="px-3.5 py-1.5 rounded-lg bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift flex items-center"
            >
              {isRegenerating ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
              Submit & Regenerate
            </button>
          </div>
        </div>
      )}

      {/* Summary */}
      <div className="p-4 rounded-xl bg-cream-50 dark:bg-charcoal-750/70 border border-sand-200/60 dark:border-charcoal-700">
        <p className="text-xs font-medium uppercase tracking-wider text-ink-500 dark:text-sand-400 mb-1">
          Executive Summary
        </p>
        <p className="text-sm text-ink-800 dark:text-sand-200 leading-relaxed font-sans">
          {recommendation.summary}
        </p>
      </div>

      {/* Action Items Checklist */}
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-ink-500 dark:text-sand-400">
          Recommended Action Checklist
        </p>
        <div className="space-y-2">
          {recommendation.actions.map((action, idx) => {
            const isDone = !!completedActions[idx];
            return (
              <div
                key={idx}
                onClick={() => toggleAction(idx)}
                className={`p-3 rounded-xl border flex items-start space-x-3 cursor-pointer transition-all ${
                  isDone
                    ? 'bg-sage-50/50 border-sage-300 dark:bg-sage-600/10 dark:border-sage-600/20 text-ink-500 dark:text-sand-400 line-through'
                    : 'bg-white dark:bg-charcoal-750 border-sand-200 dark:border-charcoal-700 hover:border-clay-300'
                }`}
              >
                <div className="mt-0.5 text-clay-500 flex-shrink-0">
                  {isDone ? (
                    <CheckSquare className="w-4 h-4 text-sage-600" />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                </div>
                <span className="text-xs text-ink-800 dark:text-sand-200 leading-relaxed">
                  {action}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Follow-up Timeline */}
      <div className="flex items-center text-xs text-ink-600 dark:text-sand-400 pt-2 border-t border-sand-200 dark:border-charcoal-700">
        <Calendar className="w-4 h-4 mr-2 text-clay-500" />
        <span>
          Suggested follow-up session: within <strong>{recommendation.follow_up_in_days} days</strong>
        </span>
      </div>
    </div>
  );
};
