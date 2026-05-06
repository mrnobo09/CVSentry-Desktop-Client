/**
 * request.ts — Unified Axios instance for the orchestrator backend.
 *
 * All API calls go through the local orchestrator (FastAPI on VITE_BACKEND_URL).
 * The orchestrator proxies auth, alerts, and node management to Django.
 *
 * Token flow:
 *   - In-memory accessToken (fast, always up-to-date after refresh)
 *   - localStorage backup (survives page reload)
 *   - Auto-refresh on 401 via orchestrator's /api/auth/refresh
 */
import axios from 'axios';
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';

interface CustomAxiosRequestConfig extends InternalAxiosRequestConfig {
    _retry?: boolean;
}

const BASE_URL = import.meta.env.VITE_BACKEND_URL as string;

let accessToken: string | null = null;

export const setAccessToken = (token: string | null) => {
    accessToken = token;
    if (token) {
        localStorage.setItem('access_token', token);
    } else {
        localStorage.removeItem('access_token');
    }
};

export const setRefreshToken = (token: string | null) => {
    if (token) {
        localStorage.setItem('refresh_token', token);
    } else {
        localStorage.removeItem('refresh_token');
    }
};

export const getAccessToken = () => accessToken;

const instance = axios.create({
    baseURL: BASE_URL,
});

instance.interceptors.request.use((config) => {
    const token = accessToken ?? localStorage.getItem('access_token');
    if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

instance.interceptors.response.use(
    (res) => res,
    async (err) => {
        const originalConfig = err.config as CustomAxiosRequestConfig;
        if (originalConfig.url?.includes('/api/auth/refresh')) {
            return Promise.reject(err);
        }
        if (err.response?.status === 401 && !originalConfig._retry) {
            originalConfig._retry = true;
            try {
                const storedRefresh = localStorage.getItem('refresh_token');
                if (!storedRefresh) throw new Error('No refresh token');

                const refreshRes = await axios.post(`${BASE_URL}/api/auth/refresh`, {
                    refresh: storedRefresh,
                });
                const newAccess = refreshRes.data.access;
                setAccessToken(newAccess);
                originalConfig.headers.Authorization = `Bearer ${newAccess}`;
                return instance(originalConfig);
            } catch {
                setAccessToken(null);
                setRefreshToken(null);
                return Promise.reject(err);
            }
        }
        return Promise.reject(err);
    },
);

const request = {
    get: async <T = any>(url: string, config: AxiosRequestConfig = {}): Promise<T> =>
        (await instance.get<T>(url, config)).data,

    post: async <T = any>(url: string, data?: any, config: AxiosRequestConfig = {}): Promise<T> =>
        (await instance.post<T>(url, data, config)).data,

    delete: async <T = any>(url: string, config: AxiosRequestConfig = {}): Promise<T> =>
        (await instance.delete<T>(url, config)).data,
};

export default request;
