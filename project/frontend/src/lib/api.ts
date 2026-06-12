import { getAccessToken, removeAccessToken } from './token';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function getErrorMessage(res: Response) {
  try {
    const data = await res.json();
    return data?.detail || data?.message || `API request failed: ${res.status}`;
  } catch {
    return `API request failed: ${res.status}`;
  }
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const token = getAccessToken();

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const res = await fetch(input, {
    ...init,
    headers,
  });

  if (res.status === 401) {
    removeAccessToken();
  }

  return res;
}

export async function apiJson<T>(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');

  const res = await apiFetch(input, {
    ...init,
    headers,
  });

  if (!res.ok) {
    throw new ApiError(await getErrorMessage(res), res.status);
  }

  return res.json() as Promise<T>;
}
