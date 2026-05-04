import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

/**
 * SyncStatusBar — A small, non-blocking indicator that shows when
 * the local face database is syncing with the cloud.
 * 
 * Appears as a subtle bar at the bottom of the screen with a spinner,
 * and disappears once the sync is complete.
 */
export default function SyncStatusBar() {
    const { isAuthenticated } = useAuth();
    const [isSyncing, setIsSyncing] = useState(false);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        if (!isAuthenticated) return;

        const FASTAPI_URL = import.meta.env.VITE_BACKEND_URL;
        let interval: ReturnType<typeof setInterval>;

        const poll = async () => {
            try {
                const res = await fetch(`${FASTAPI_URL}/sync/status`);
                const data = await res.json();
                setIsSyncing(data.is_syncing);

                if (data.is_syncing) {
                    setVisible(true);
                } else if (visible) {
                    // Keep visible briefly after sync completes for smooth UX
                    setTimeout(() => setVisible(false), 1500);
                }
            } catch {
                // Silently fail — not critical
            }
        };

        poll();
        interval = setInterval(poll, 3000);

        return () => clearInterval(interval);
    }, [isAuthenticated, visible]);

    if (!visible) return null;

    return (
        <div
            style={{
                position: 'fixed',
                bottom: 0,
                left: 0,
                right: 0,
                height: '36px',
                background: 'rgba(15, 23, 42, 0.92)',
                backdropFilter: 'blur(8px)',
                borderTop: '1px solid rgba(99, 102, 241, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px',
                zIndex: 9999,
                transition: 'opacity 0.3s ease',
                opacity: visible ? 1 : 0,
            }}
        >
            {isSyncing ? (
                <>
                    <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        style={{ animation: 'spin 1s linear infinite' }}
                    >
                        <circle cx="12" cy="12" r="10" stroke="rgba(99,102,241,0.4)" strokeWidth="3" />
                        <path
                            d="M12 2a10 10 0 0 1 10 10"
                            stroke="#818cf8"
                            strokeWidth="3"
                            strokeLinecap="round"
                        />
                    </svg>
                    <span style={{ color: '#a5b4fc', fontSize: '12px', fontWeight: 500 }}>
                        Syncing face database…
                    </span>
                </>
            ) : (
                <span style={{ color: '#6ee7b7', fontSize: '12px', fontWeight: 500 }}>
                    ✓ Face database synced
                </span>
            )}
            <style>{`
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
}
