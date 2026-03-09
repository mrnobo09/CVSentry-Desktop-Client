import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import authRequest, { setAccessToken } from '../utils/authRequest';

interface AuthContextType {
    isAuthenticated: boolean | null;
    setIsAuthenticated: (v: boolean) => void;
    checkAuth: () => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

    const checkAuth = useCallback(async () => {
        try {
            const user = await authRequest.get('/auth/users/me/');
            setIsAuthenticated(!!user?.id);

            // Important: Re-register the node with the FastAPI backend on startup
            // so that heartbeat tasks have the access token even after a refresh/restart.
            const storedToken = localStorage.getItem('access_token');
            if (user?.id && storedToken) {
                const FASTAPI_URL = import.meta.env.VITE_BACKEND_URL;
                fetch(`${FASTAPI_URL}/node/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ access_token: storedToken }),
                }).catch(() => {});
            }
        } catch {
            setIsAuthenticated(false);
        }
    }, []);

    const logout = useCallback(() => {
        localStorage.removeItem('access_token');
        setAccessToken(null);
        setIsAuthenticated(false);
    }, []);

    useEffect(() => {
        // Restore in-memory token from localStorage on page load so that
        // both authRequest and request.ts have the current token immediately.
        const stored = localStorage.getItem('access_token');
        if (stored) {
            setAccessToken(stored);
        }
        checkAuth();
    }, [checkAuth]);

    return (
        <AuthContext.Provider value={{ isAuthenticated, setIsAuthenticated, checkAuth, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
}
