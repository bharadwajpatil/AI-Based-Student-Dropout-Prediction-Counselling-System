import { apiClient } from './client';
import type { NotificationItem } from '../types';

export const notificationApi = {
  async getNotifications(params: { unread_only?: boolean; limit?: number; skip?: number } = {}): Promise<{
    notifications: NotificationItem[];
    total: number;
    unread_count: number;
  }> {
    const query = new URLSearchParams();
    if (params.unread_only) query.set('unread_only', 'true');
    if (params.limit) query.set('limit', params.limit.toString());
    if (params.skip) query.set('skip', params.skip.toString());

    const qs = query.toString();
    return apiClient(`/notifications${qs ? `?${qs}` : ''}`);
  },

  async getUnreadCount(): Promise<{ unread_count: number }> {
    return apiClient('/notifications/unread-count');
  },

  async markRead(id: string): Promise<{ success: boolean }> {
    return apiClient(`/notifications/${id}/read`, { method: 'PATCH' });
  },

  async markAllRead(): Promise<{ success: boolean; modified_count: number }> {
    return apiClient('/notifications/read-all', { method: 'POST' });
  },
};
