import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import authRequest, { setAccessToken } from '../utils/authRequest';

interface AuthContextType {
    isAuthenticated: boolean | null;
    setIsAuthenticated: (v: boolean) => void;
    checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

    const checkAuth = useCallback(async () => {
        try {
            const user = await authRequest.get('/auth/users/me/');
            setIsAuthenticated(!!user?.id);
        } catch {
            setIsAuthenticated(false);
        }
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
        <AuthContext.Provider value={{ isAuthenticated, setIsAuthenticated, checkAuth }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
}
