/**
 * authRequest.ts — Axios instance for the Django backend.
 *
 * Desktop Client auth flow uses /auth/desktop/* endpoints:
 *   - verify-otp → returns { access, refresh } in body (no cookie)
 *   - token/refresh → accepts { refresh } in body (no cookie)
 *
 * Dashboard auth flow uses /auth/verify-otp/ and /auth/token/refresh/ (cookie-based).
 * This file is used only by the Desktop Client, so it targets the desktop endpoints.
 */
import axios from 'axios';
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';

interface CustomAxiosRequestConfig extends InternalAxiosRequestConfig {
    _retry?: boolean;
}

const DJANGO_URL = import.meta.env.VITE_DJANGO_URL as string;

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

const authAxios = axios.create({
    baseURL: DJANGO_URL,
    // No withCredentials needed — Desktop Client uses body tokens, not cookies
});

authAxios.interceptors.request.use((config) => {
    if (accessToken && config.headers) {
        config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
});

authAxios.interceptors.response.use(
    (res) => res,
    async (err) => {
        const originalConfig = err.config as CustomAxiosRequestConfig;
        if (originalConfig.url?.includes('/auth/desktop/token/refresh/')) {
            return Promise.reject(err);
        }
        if (err.response?.status === 401 && !originalConfig._retry) {
            originalConfig._retry = true;
            try {
                const storedRefresh = localStorage.getItem('refresh_token');
                if (!storedRefresh) throw new Error('No refresh token');

                // Desktop endpoint: refresh token in request body
                const refreshRes = await authAxios.post('/auth/desktop/token/refresh/', {
                    refresh: storedRefresh,
                });
                const newAccess = refreshRes.data.access;
                setAccessToken(newAccess); // also syncs localStorage
                originalConfig.headers.Authorization = `Bearer ${newAccess}`;
                return authAxios(originalConfig);
            } catch {
                setAccessToken(null);
                setRefreshToken(null);
                return Promise.reject(err);
            }
        }
        return Promise.reject(err);
    }
);

const authRequest = {
    get: async <T = any>(url: string, config: AxiosRequestConfig = {}): Promise<T> =>
        (await authAxios.get<T>(url, config)).data,

    post: async <T = any>(url: string, data?: any, config: AxiosRequestConfig = {}): Promise<T> =>
        (await authAxios.post<T>(url, data, config)).data,
};

export default authRequest;
