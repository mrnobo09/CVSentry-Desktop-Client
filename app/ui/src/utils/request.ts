/**
 * request.ts — Axios instance for the LOCAL FastAPI backend.
 *
 * Reads the token from:
 *  1. getAccessToken() — the shared in-memory variable (always up-to-date after refresh)
 *  2. localStorage fallback — for the first request on a hard page reload, before
 *     AuthContext has restored the in-memory token
 */
import axios from 'axios';
import type { AxiosRequestConfig } from 'axios';
import { getAccessToken } from './authRequest';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL as string;

const instance = axios.create({
    baseURL: BACKEND_URL,
});

instance.interceptors.request.use((config) => {
    // Prefer in-memory (always refreshed), fall back to localStorage
    const token = getAccessToken() ?? localStorage.getItem('access_token');
    if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

const request = {
    get: async <T = any>(url: string, config: AxiosRequestConfig = {}): Promise<T> =>
        (await instance.get<T>(url, config)).data,

    post: async <T = any>(url: string, data?: any, config: AxiosRequestConfig = {}): Promise<T> =>
        (await instance.post<T>(url, data, config)).data,

    delete: async <T = any>(url: string, config: AxiosRequestConfig = {}): Promise<T> =>
        (await instance.delete<T>(url, config)).data,
};

export default request;
