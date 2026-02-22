/**
 * Axios instance for the local Desktop Client FastAPI backend.
 * Automatically attaches the Django JWT access token stored in localStorage.
 */
import axios from 'axios';
import type { AxiosRequestConfig } from 'axios';

const FASTAPI_URL = import.meta.env.VITE_BACKEND_URL as string;

const localAxios = axios.create({
    baseURL: FASTAPI_URL,
});

// Inject the token from localStorage before every request
localAxios.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

const localRequest = {
    get: async <T = any>(url: string, config: AxiosRequestConfig = {}): Promise<T> =>
        (await localAxios.get<T>(url, config)).data,

    post: async <T = any>(url: string, data?: any, config: AxiosRequestConfig = {}): Promise<T> =>
        (await localAxios.post<T>(url, data, config)).data,
};

export default localRequest;
