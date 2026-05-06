import { useState, useEffect, useRef, useCallback } from 'react';
import request from '../utils/request';

export interface Alert {
    id: number;
    node_label: string;
    node_ip: string;
    camera_id: string;
    frame_id: string;
    alert_type: string;
    identities: string[];
    timestamp: string;
    created_at: string;
}

interface UseAlertsResult {
    latestAlert: Alert | null;
    unreadCount: number;
    clearLatest: () => void;
}

const POLL_INTERVAL_MS = 5000;

let alertAudio: HTMLAudioElement | null = null;
function playAlertSound() {
    try {
        if (!alertAudio) {
            alertAudio = new Audio('/alert.mp3');
            alertAudio.volume = 0.9;
        }
        alertAudio.currentTime = 0;
        alertAudio.play().catch(() => {});
    } catch { /**/ }
}

export function useAlerts(): UseAlertsResult {
    const [latestAlert, setLatestAlert] = useState<Alert | null>(null);
    const [unreadCount, setUnreadCount] = useState(0);
    const sinceRef = useRef<string | null>(null);
    const initialLoad = useRef(true);

    const fetchAlerts = useCallback(async () => {
        try {
            const params = sinceRef.current
                ? `?since=${encodeURIComponent(sinceRef.current)}&limit=10`
                : '?limit=10';
            const data: Alert[] = await request.get(`/api/auth/alerts${params}`);

            if (data && data.length > 0) {
                sinceRef.current = data[0].timestamp;

                if (initialLoad.current) {
                    initialLoad.current = false;
                    return;
                }

                const newest = data[0];
                setLatestAlert(newest);
                setUnreadCount(c => c + data.length);
                if (['COMBINED_THREAT', 'WEAPON_DETECTED', 'FACE_RECOGNIZED'].includes(newest.alert_type)) {
                    playAlertSound();
                }
            } else {
                initialLoad.current = false;
            }
        } catch { /**/ }
    }, []);

    useEffect(() => {
        fetchAlerts();
        const id = setInterval(fetchAlerts, POLL_INTERVAL_MS);
        return () => clearInterval(id);
    }, [fetchAlerts]);

    const clearLatest = useCallback(() => {
        setLatestAlert(null);
        setUnreadCount(0);
    }, []);

    return { latestAlert, unreadCount, clearLatest };
}
