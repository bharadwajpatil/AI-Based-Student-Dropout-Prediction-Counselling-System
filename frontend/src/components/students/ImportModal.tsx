import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { studentApi } from '../../api/students';
import { useToast } from '../../context/ToastContext';
import { useRealtime } from '../../hooks/useRealtime';
import { UploadCloud, CheckCircle2, AlertCircle, FileText, Loader2 } from 'lucide-react';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}

export const ImportModal: React.FC<ImportModalProps> = ({
  isOpen,
  onClose,
  onImportComplete,
}) => {
  const { success, error } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<{
    processed: number;
    total: number;
    successful: number;
    failed: number;
    is_complete: boolean;
  } | null>(null);

  // Listen for real-time import progress via SSE
  useRealtime({
    onImportProgress: (data) => {
      if (jobId && data.job_id === jobId) {
        setProgress(data);
        if (data.is_complete) {
          setUploading(false);
          success(
            'Import Completed',
            `Processed ${data.total} students (${data.successful} successful, ${data.failed} failed).`
          );
          onImportComplete();
        }
      }
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setProgress({ processed: 0, total: 100, successful: 0, failed: 0, is_complete: false });

    try {
      const res = await studentApi.importStudentsCsv(file);
      setJobId(res.job_id);
    } catch (err) {
      setUploading(false);
      const msg = err instanceof Error ? err.message : 'Upload failed';
      error('Import Failed', msg);
    }
  };

  const handleReset = () => {
    setFile(null);
    setJobId(null);
    setProgress(null);
    setUploading(false);
  };

  const percentage = progress && progress.total > 0
    ? Math.min(Math.round((progress.processed / progress.total) * 100), 100)
    : 0;

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        handleReset();
        onClose();
      }}
      title="Bulk Import Students"
      description="Upload a CSV spreadsheet containing student demographic and academic records."
      maxWidth="lg"
    >
      <div className="space-y-5">
        {!progress ? (
          <div>
            <label className="border-2 border-dashed border-sand-300 dark:border-charcoal-700 rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer hover:border-clay-400 dark:hover:border-clay-500 bg-cream-50/50 dark:bg-charcoal-800/50 transition-colors">
              <UploadCloud className="w-10 h-10 text-clay-500 mb-3" />
              <p className="text-sm font-semibold text-ink-900 dark:text-sand-100">
                {file ? file.name : 'Click to browse or drop CSV file'}
              </p>
              <p className="text-xs text-ink-500 dark:text-sand-400 mt-1">
                Required columns: erp_id, name, department, semester, batch
              </p>
              <input
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>

            {file && (
              <div className="mt-4 flex items-center justify-between p-3 rounded-xl bg-sand-100 dark:bg-charcoal-750">
                <div className="flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-clay-500" />
                  <span className="text-xs font-medium text-ink-900 dark:text-sand-100 truncate max-w-xs">
                    {file.name}
                  </span>
                  <span className="text-[10px] text-ink-500">
                    ({(file.size / 1024).toFixed(1)} KB)
                  </span>
                </div>
                <button
                  onClick={() => setFile(null)}
                  className="text-xs text-rose-500 hover:text-rose-600 font-medium"
                >
                  Remove
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4 py-2">
            <div className="flex justify-between items-center text-xs font-semibold text-ink-700 dark:text-sand-300">
              <span>Import Progress</span>
              <span>
                {progress.processed} / {progress.total} rows ({percentage}%)
              </span>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-sand-200 dark:bg-charcoal-700 rounded-full h-3 overflow-hidden">
              <div
                className="bg-clay-500 h-3 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${percentage}%` }}
              />
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="p-3 rounded-xl bg-sage-50 dark:bg-sage-600/10 border border-sage-200 dark:border-sage-600/20 flex items-center space-x-3">
                <CheckCircle2 className="w-5 h-5 text-sage-600" />
                <div>
                  <p className="text-[11px] text-ink-500 dark:text-sand-400 font-medium">Successful</p>
                  <p className="text-base font-bold text-sage-600">{progress.successful}</p>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-600/10 border border-rose-200 dark:border-rose-600/20 flex items-center space-x-3">
                <AlertCircle className="w-5 h-5 text-rose-600" />
                <div>
                  <p className="text-[11px] text-ink-500 dark:text-sand-400 font-medium">Failed</p>
                  <p className="text-base font-bold text-rose-600">{progress.failed}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex justify-end space-x-3 pt-3 border-t border-sand-200 dark:border-charcoal-700">
          <button
            type="button"
            onClick={() => {
              handleReset();
              onClose();
            }}
            className="px-4 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 text-ink-700 dark:text-sand-300 text-sm font-medium hover:bg-sand-100 dark:hover:bg-charcoal-800 transition-colors"
          >
            {progress?.is_complete ? 'Close' : 'Cancel'}
          </button>

          {!progress && (
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-sm font-semibold shadow-soft card-lift disabled:opacity-60 transition-all"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Uploading...
                </>
              ) : (
                'Start Import'
              )}
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
};
