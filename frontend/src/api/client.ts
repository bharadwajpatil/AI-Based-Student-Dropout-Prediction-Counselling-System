export const API_BASE = '/api/v1';

const ACCESS_TOKEN_KEY = 'beacon_access_token';
const REFRESH_TOKEN_KEY = 'beacon_refresh_token';

export const getAccessToken = (): string | null => localStorage.getItem(ACCESS_TOKEN_KEY);
export const getRefreshToken = (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY);

export const setTokens = (accessToken: string, refreshToken?: string): void => {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
};

export const clearTokens = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

const subscribeTokenRefresh = (cb: (token: string) => void) => {
  refreshSubscribers.push(cb);
};

const onTokenRefreshed = (token: string) => {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
};

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit & { ifMatch?: string | number } = {}
): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const token = getAccessToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (options.ifMatch !== undefined) {
    headers.set('If-Match', `"${options.ifMatch}"`);
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Network connection failure';
    throw new ApiError(0, errorMsg);
  }

  // Handle Token Expiry & Automatic Refresh Rotation
  if (response.status === 401 && getRefreshToken() && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: getRefreshToken() }),
        });

        if (refreshRes.ok) {
          const data = await refreshRes.json();
          setTokens(data.access_token, data.refresh_token);
          onTokenRefreshed(data.access_token);
        } else {
          clearTokens();
          window.location.href = '/login?expired=1';
          throw new ApiError(401, 'Session expired. Please log in again.');
        }
      } catch (refreshErr) {
        clearTokens();
        window.location.href = '/login?expired=1';
        throw refreshErr;
      } finally {
        isRefreshing = false;
      }
    }

    // Wait for the refresh to finish then retry
    return new Promise((resolve, reject) => {
      subscribeTokenRefresh((newToken) => {
        headers.set('Authorization', `Bearer ${newToken}`);
        fetch(url, { ...options, headers })
          .then(async (retryRes) => {
            if (!retryRes.ok) {
              const errBody = await retryRes.json().catch(() => null);
              reject(new ApiError(retryRes.status, errBody?.detail || 'Request failed', errBody));
            } else {
              const data = await retryRes.json().catch(() => null);
              resolve(data as T);
            }
          })
          .catch(reject);
      });
    });
  }

  if (!response.ok) {
    let errorMessage = `HTTP Error ${response.status}`;
    let errBody: unknown = null;
    try {
      errBody = await response.json();
      if (errBody && typeof errBody === 'object' && 'detail' in errBody) {
        const detail = (errBody as { detail: unknown }).detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (Array.isArray(detail) && detail[0]?.msg) {
          errorMessage = detail[0].msg;
        }
      }
    } catch {
      // Non-JSON response
      errorMessage = await response.text().catch(() => errorMessage);
    }
    throw new ApiError(response.status, errorMessage, errBody);
  }

  // Handle empty responses
  if (response.status === 204) {
    return {} as T;
  }

  // Return text or blob if requested
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('text/csv')) {
    const blob = await response.blob();
    return blob as unknown as T;
  }

  return response.json();
}
