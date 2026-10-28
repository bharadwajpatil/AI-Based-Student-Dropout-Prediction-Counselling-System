import React, { useState, useEffect, useCallback } from 'react';
import { counsellingApi } from '../../api/counselling';
import type { CounsellingCase, CounsellingStatus } from '../../types';
import { RiskBadge } from '../../components/common/RiskBadge';
import { SkeletonTable } from '../../components/common/Skeleton';
import { AiRecommendationCard } from '../../components/counselling/AiRecommendationCard';
import { CaseTimeline } from '../../components/counselling/CaseTimeline';
import { CrisisBanner } from '../../components/counselling/CrisisBanner';
import { Modal } from '../../components/common/Modal';
import { useToast } from '../../context/ToastContext';
import {
  HeartHandshake,
  CheckCircle2,
  Clock,
  ArrowRight,
  Filter,
} from 'lucide-react';

export const CounsellingPage: React.FC = () => {
  const { success, error } = useToast();

  const [cases, setCases] = useState<CounsellingCase[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedStatus, setSelectedStatus] = useState<CounsellingStatus | 'all'>('all');
  const [activeCase, setActiveCase] = useState<CounsellingCase | null>(null);

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const res = await counsellingApi.getCases({
        status: selectedStatus === 'all' ? undefined : selectedStatus,
        page_size: 30,
      });
      setCases(res.items);
    } catch (err) {
      console.error('Failed to load counselling cases', err);
    } finally {
      setLoading(false);
    }
  }, [selectedStatus]);

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  const handleStatusChange = async (caseId: string, newStatus: CounsellingStatus) => {
    try {
      const updated = await counsellingApi.updateCase(caseId, { status: newStatus });
      success('Status Updated', `Case marked as ${newStatus}.`);
      setCases((prev) => prev.map((c) => (c.id === caseId ? updated : c)));
      if (activeCase?.id === caseId) {
        setActiveCase(updated);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Update failed';
      error('Failed to Update', msg);
    }
  };

  const handleGenerateAi = async (notes?: string) => {
    if (!activeCase) return;
    try {
      const updated = await counsellingApi.generateRecommendation(activeCase.student_id, {
        teacher_notes: notes,
        force_regenerate: true,
      });
      setActiveCase(updated);
      setCases((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      success('AI Intervention Updated', 'Personalized recommendations generated.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Generation failed';
      error('Generation Failed', msg);
    }
  };

  const handleAddNote = async (content: string) => {
    if (!activeCase) return;
    try {
      const updated = await counsellingApi.addNote(activeCase.id, content);
      setActiveCase(updated);
      setCases((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      success('Meeting Note Saved', 'Timeline updated with append-only log.');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save note';
      error('Note Failed', msg);
    }
  };

  const statusTabs: { label: string; value: CounsellingStatus | 'all'; icon: React.ReactNode }[] = [
    { label: 'All Cases', value: 'all', icon: <Filter className="w-3.5 h-3.5 mr-1.5" /> },
    { label: 'Pending', value: 'pending', icon: <Clock className="w-3.5 h-3.5 mr-1.5 text-amber-500" /> },
    { label: 'In Progress', value: 'in_progress', icon: <Clock className="w-3.5 h-3.5 mr-1.5 text-clay-500" /> },
    { label: 'Follow Up', value: 'follow_up', icon: <Clock className="w-3.5 h-3.5 mr-1.5 text-clay-400" /> },
    { label: 'Resolved', value: 'resolved', icon: <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-sage-600" /> },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-sand-200 dark:border-charcoal-800">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100 flex items-center">
            <HeartHandshake className="w-7 h-7 mr-2.5 text-clay-500" />
            AI Mentorship & Counselling Hub
          </h1>
          <p className="text-xs sm:text-sm text-ink-500 dark:text-sand-400 mt-1">
            Track student intervention workflows, generate Gemini AI action plans, and maintain session timelines.
          </p>
        </div>
      </div>

      {/* Status Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        {statusTabs.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setSelectedStatus(tab.value)}
            className={`inline-flex items-center px-4 py-2 rounded-xl text-xs font-semibold border transition-all ${
              selectedStatus === tab.value
                ? 'bg-clay-500 text-white border-clay-500 shadow-soft'
                : 'bg-white dark:bg-charcoal-800 text-ink-700 dark:text-sand-300 border-sand-200 dark:border-charcoal-700 hover:bg-sand-100'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Cases Table */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden">
        {loading ? (
          <SkeletonTable rows={6} />
        ) : cases.length === 0 ? (
          <div className="p-12 text-center text-xs text-ink-500 dark:text-sand-400 space-y-2">
            <HeartHandshake className="w-8 h-8 mx-auto text-sand-400" />
            <p className="font-semibold text-sm text-ink-900 dark:text-sand-100">
              No counselling cases found under this status.
            </p>
            <p>Cases are automatically created whenever student performance escalates to High Risk.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-50 dark:bg-charcoal-750 text-ink-600 dark:text-sand-400 uppercase font-semibold">
                <tr>
                  <th className="px-5 py-3.5">Student</th>
                  <th className="px-5 py-3.5">Risk Tier</th>
                  <th className="px-5 py-3.5">Workflow Status</th>
                  <th className="px-5 py-3.5">AI Intervention</th>
                  <th className="px-5 py-3.5">Timeline Notes</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-200 dark:divide-charcoal-700 text-ink-900 dark:text-sand-100">
                {cases.map((c) => (
                  <tr
                    key={c.id}
                    className="hover:bg-cream-50/50 dark:hover:bg-charcoal-750/50 transition-colors cursor-pointer"
                    onClick={() => setActiveCase(c)}
                  >
                    <td className="px-5 py-4 font-semibold">
                      <div className="font-medium text-ink-900 dark:text-sand-100">
                        {c.student_name || 'Assigned Student'}
                      </div>
                      <div className="text-[11px] font-mono text-ink-500 dark:text-sand-400">
                        {c.student_erp || c.student_id}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <RiskBadge level={c.risk_level} isEscalated={c.risk_level === 'High'} />
                    </td>
                    <td className="px-5 py-4">
                      <span className="capitalize font-semibold text-xs px-2.5 py-1 rounded-full bg-cream-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 border border-sand-200 dark:border-charcoal-600">
                        {c.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      {c.ai_recommendation ? (
                        <span className="text-[11px] font-medium text-ink-700 dark:text-sand-300">
                          {c.ai_recommendation.ai_source === 'gemini' ? 'Gemini AI Plan' : 'Template Plan'}
                        </span>
                      ) : (
                        <span className="text-[11px] text-ink-400">Not generated</span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-ink-600 dark:text-sand-300">
                      {c.notes_timeline.length} session note(s)
                    </td>
                    <td className="px-5 py-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveCase(c);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-clay-500 hover:bg-clay-600 text-white font-semibold text-xs shadow-soft card-lift transition-all"
                      >
                        Open Case <ArrowRight className="w-3.5 h-3.5 inline ml-1" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Case Detail Modal */}
      {activeCase && (
        <Modal
          isOpen={!!activeCase}
          onClose={() => setActiveCase(null)}
          title={`Intervention Case — ${activeCase.student_name || 'Student'}`}
          description={`ERP ID: ${activeCase.student_erp || activeCase.student_id} • Current Risk: ${activeCase.risk_level}`}
          maxWidth="2xl"
        >
          <div className="space-y-6">
            {/* Status Stepper */}
            <div className="p-4 rounded-xl bg-cream-50 dark:bg-charcoal-750 border border-sand-200 dark:border-charcoal-700">
              <label className="block text-xs font-semibold text-ink-700 dark:text-sand-300 mb-2">
                Update Case Workflow Lifecycle
              </label>
              <div className="grid grid-cols-4 gap-2">
                {(['pending', 'in_progress', 'follow_up', 'resolved'] as CounsellingStatus[]).map(
                  (st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => handleStatusChange(activeCase.id, st)}
                      className={`py-2 px-1 text-[11px] font-semibold rounded-xl border capitalize transition-all ${
                        activeCase.status === st
                          ? 'bg-clay-500 text-white border-clay-500 shadow-soft'
                          : 'bg-white dark:bg-charcoal-800 text-ink-700 dark:text-sand-300 border-sand-300 dark:border-charcoal-700 hover:bg-sand-100'
                      }`}
                    >
                      {st.replace('_', ' ')}
                    </button>
                  )
                )}
              </div>
            </div>

            {/* Crisis Alert Banner */}
            <CrisisBanner
              escalateToHod={activeCase.escalate_to_hod}
              referToCounsellor={activeCase.refer_to_counsellor}
            />

            {/* AI Recommendation */}
            <AiRecommendationCard
              recommendation={activeCase.ai_recommendation}
              onRegenerate={handleGenerateAi}
            />

            {/* Timeline Notes */}
            <CaseTimeline
              notes={activeCase.notes_timeline}
              onAddNote={handleAddNote}
            />
          </div>
        </Modal>
      )}
    </div>
  );
};
