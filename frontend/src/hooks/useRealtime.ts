import { useEffect, useRef, useCallback } from 'react';
import { getAccessToken, API_BASE } from '../api/client';
import { useToast } from '../context/ToastContext';

export interface RealtimeHandlers {
  onRiskChanged?: (data: { student_id: string; old_level?: string; new_level: string; score: number }) => void;
  onImportProgress?: (data: { job_id: string; processed: number; total: number; successful: number; failed: number; is_complete: boolean }) => void;
  onNotificationNew?: (data: { id: string; title: string; message: string; type: string }) => void;
  onCounsellingAssigned?: (data: { case_id: string; student_id: string; student_name?: string }) => void;
}

export function useRealtime(handlers: RealtimeHandlers = {}) {
  const { info, warning } = useToast();
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef<number>(1000);
  const handlersRef = useRef<RealtimeHandlers>(handlers);

  // Keep handlers updated without re-triggering the connection
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    const token = getAccessToken();
    if (!token) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const sseUrl = `${API_BASE}/events?token=${encodeURIComponent(token)}`;
    const es = new EventSource(sseUrl);
    eventSourceRef.current = es;

    es.onopen = () => {
      reconnectDelayRef.current = 1000; // Reset backoff
    };

    es.addEventListener('risk.changed', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data.new_level === 'High') {
          warning('High Risk Alert', `Student risk escalated to High (${data.score?.toFixed(1) || ''}%)`);
        } else {
          info('Risk Updated', `Student risk transitioned to ${data.new_level}`);
        }
        handlersRef.current.onRiskChanged?.(data);
      } catch (err) {
        console.error('Failed to parse risk.changed event', err);
      }
    });

    es.addEventListener('import.progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        handlersRef.current.onImportProgress?.(data);
      } catch (err) {
        console.error('Failed to parse import.progress event', err);
      }
    });

    es.addEventListener('notification.new', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        info(data.title, data.message);
        handlersRef.current.onNotificationNew?.(data);
      } catch (err) {
        console.error('Failed to parse notification.new event', err);
      }
    });

    es.addEventListener('counselling.assigned', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        info('New Counselling Assignment', `You have been assigned to counsel student ${data.student_name || ''}`);
        handlersRef.current.onCounsellingAssigned?.(data);
      } catch (err) {
        console.error('Failed to parse counselling.assigned event', err);
      }
    });

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;
      // Exponential backoff reconnect
      const delay = Math.min(reconnectDelayRef.current * 1.5, 30000);
      reconnectDelayRef.current = delay;
      reconnectTimeoutRef.current = setTimeout(() => {
        connectRef.current();
      }, delay);
    };
  }, [info, warning]);

  useEffect(() => {
    connectRef.current = connect;
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [connect]);

  return {
    reconnect: connect,
  };
}
