import React, { useState } from 'react';
import { Send, Clock, User, MessageSquare } from 'lucide-react';
import type { TimelineNote } from '../../types';

interface CaseTimelineProps {
  notes: TimelineNote[];
  onAddNote: (content: string) => Promise<void>;
  loading?: boolean;
}

export const CaseTimeline: React.FC<CaseTimelineProps> = ({
  notes,
  onAddNote,
  loading = false,
}) => {
  const [content, setContent] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    setSubmitting(true);
    try {
      await onAddNote(content.trim());
      setContent('');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-sand-200 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 p-6 shadow-soft space-y-6">
      <div className="flex items-center space-x-2">
        <div className="p-2 rounded-xl bg-cream-100 dark:bg-charcoal-750 text-clay-500">
          <MessageSquare className="w-5 h-5" />
        </div>
        <div>
          <h4 className="font-display font-semibold text-base text-ink-900 dark:text-sand-100">
            Meeting Notes & Timeline
          </h4>
          <p className="text-xs text-ink-500 dark:text-sand-400">
            Append-only chronological audit trail of faculty and mentor sessions.
          </p>
        </div>
      </div>

      {/* Timeline items */}
      <div className="space-y-4 max-h-96 overflow-y-auto pr-1">
        {notes.length === 0 ? (
          <div className="p-6 text-center text-xs text-ink-500 dark:text-sand-400 bg-sand-50 dark:bg-charcoal-750 rounded-xl border border-dashed border-sand-300 dark:border-charcoal-700">
            No meeting notes recorded yet. Record the first discussion log below.
          </div>
        ) : (
          notes.map((note) => (
            <div
              key={note.note_id}
              className="p-4 rounded-xl bg-cream-50/60 dark:bg-charcoal-750 border border-sand-200 dark:border-charcoal-700 space-y-2 animate-fade-up"
            >
              <div className="flex items-center justify-between text-xs text-ink-500 dark:text-sand-400">
                <div className="flex items-center space-x-1.5 font-semibold text-ink-800 dark:text-sand-200">
                  <User className="w-3.5 h-3.5 text-clay-500" />
                  <span>{note.author_name || 'Faculty Mentor'}</span>
                </div>
                <div className="flex items-center space-x-1 text-[11px]">
                  <Clock className="w-3.5 h-3.5" />
                  <span>
                    {new Date(note.timestamp).toLocaleDateString([], {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              </div>
              <p className="text-xs text-ink-800 dark:text-sand-100 whitespace-pre-wrap leading-relaxed">
                {note.note}
              </p>
            </div>
          ))
        )}
      </div>

      {/* Add note input */}
      <form onSubmit={handleSubmit} className="space-y-3 pt-2 border-t border-sand-200 dark:border-charcoal-700">
        <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300">
          Record Session Notes
        </label>
        <textarea
          rows={3}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Document discussion points, agreed student goals, action items..."
          required
          className="w-full p-3 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 text-xs text-ink-900 dark:text-sand-100 placeholder-ink-400 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
        />
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={submitting || !content.trim() || loading}
            className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift disabled:opacity-60 transition-all"
          >
            <Send className="w-3.5 h-3.5 mr-1.5" />
            {submitting ? 'Adding...' : 'Save Note'}
          </button>
        </div>
      </form>
    </div>
  );
};
