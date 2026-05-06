import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import request, { setAccessToken } from '../utils/request';

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
            const user = await request.get('/api/auth/me');
            setIsAuthenticated(!!user?.id);
        } catch {
            setIsAuthenticated(false);
        }
    }, []);

    const logout = useCallback(() => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        setAccessToken(null);
        setIsAuthenticated(false);
    }, []);

    useEffect(() => {
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
