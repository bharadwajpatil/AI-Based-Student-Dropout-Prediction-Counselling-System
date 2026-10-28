import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { X, CheckCircle, AlertTriangle, AlertCircle, Info } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

interface ToastContextType {
  addToast: (toast: Omit<ToastItem, 'id'>) => void;
  removeToast: (id: string) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const removeToast = useCallback((id: string) => {
    if (timersRef.current.has(id)) {
      clearTimeout(timersRef.current.get(id)!);
      timersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    ({ type, title, message, duration = 4000 }: Omit<ToastItem, 'id'>) => {
      const id = Math.random().toString(36).substring(2, 9);
      const newToast: ToastItem = { id, type, title, message, duration };

      setToasts((prev) => [...prev, newToast]);

      const timer = setTimeout(() => {
        removeToast(id);
      }, duration);

      timersRef.current.set(id, timer);
    },
    [removeToast]
  );

  const pauseTimer = (id: string) => {
    if (timersRef.current.has(id)) {
      clearTimeout(timersRef.current.get(id)!);
      timersRef.current.delete(id);
    }
  };

  const resumeTimer = (toast: ToastItem) => {
    if (!timersRef.current.has(toast.id)) {
      const timer = setTimeout(() => {
        removeToast(toast.id);
      }, toast.duration || 4000);
      timersRef.current.set(toast.id, timer);
    }
  };

  const success = useCallback((title: string, message?: string) => addToast({ type: 'success', title, message }), [addToast]);
  const error = useCallback((title: string, message?: string) => addToast({ type: 'error', title, message }), [addToast]);
  const warning = useCallback((title: string, message?: string) => addToast({ type: 'warning', title, message }), [addToast]);
  const info = useCallback((title: string, message?: string) => addToast({ type: 'info', title, message }), [addToast]);

  const getToastStyle = (type: ToastType) => {
    switch (type) {
      case 'success':
        return 'bg-sage-50 border-sage-400 text-sage-600 dark:bg-charcoal-800 dark:border-sage-500';
      case 'error':
        return 'bg-rose-50 border-rose-400 text-rose-600 dark:bg-charcoal-800 dark:border-rose-500';
      case 'warning':
        return 'bg-amber-50 border-amber-400 text-amber-600 dark:bg-charcoal-800 dark:border-amber-500';
      case 'info':
        return 'bg-cream-100 border-clay-400 text-clay-600 dark:bg-charcoal-800 dark:border-clay-500';
    }
  };

  const getToastIcon = (type: ToastType) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-sage-600 flex-shrink-0" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />;
      case 'info':
        return <Info className="w-5 h-5 text-clay-500 flex-shrink-0" />;
    }
  };

  return (
    <ToastContext.Provider value={{ addToast, removeToast, success, error, warning, info }}>
      {children}
      {/* Toast Notification Container */}
      <div
        aria-live="polite"
        className="fixed top-4 right-4 z-50 flex flex-col space-y-2 pointer-events-none max-w-sm w-full"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            onMouseEnter={() => pauseTimer(toast.id)}
            onMouseLeave={() => resumeTimer(toast)}
            className={`pointer-events-auto flex items-start p-4 rounded-xl border shadow-lift animate-fade-up transition-all ${getToastStyle(
              toast.type
            )}`}
          >
            <div className="mr-3 mt-0.5">{getToastIcon(toast.type)}</div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm text-ink-900 dark:text-sand-100">{toast.title}</p>
              {toast.message && (
                <p className="mt-1 text-xs text-ink-700 dark:text-sand-300 leading-relaxed">
                  {toast.message}
                </p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="ml-3 text-sand-400 hover:text-ink-700 dark:hover:text-sand-200 transition-colors"
              aria-label="Dismiss notification"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
