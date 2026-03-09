import { useEffect, useState } from 'react';
import { AlertTriangle, X, Camera, User } from 'lucide-react';
import type { Alert } from '../hooks/useAlerts';

interface ThreatOverlayProps {
    alert: Alert;
    onDismiss: () => void;
}

const AUTO_DISMISS_MS = 10000;

export default function ThreatOverlay({ alert, onDismiss }: ThreatOverlayProps) {
    const [visible, setVisible] = useState(false);
    const [progress, setProgress] = useState(100);

    useEffect(() => {
        requestAnimationFrame(() => setVisible(true));

        const start = Date.now();
        const tick = setInterval(() => {
            const pct = Math.max(0, 100 - ((Date.now() - start) / AUTO_DISMISS_MS) * 100);
            setProgress(pct);
            if (pct === 0) { clearInterval(tick); handleDismiss(); }
        }, 50);

        return () => clearInterval(tick);
    }, []);

    const handleDismiss = () => {
        setVisible(false);
        setTimeout(onDismiss, 300);
    };

    const isCombined = alert.alert_type === 'COMBINED_THREAT';
    const isFace = alert.alert_type === 'FACE_RECOGNIZED';

    let containerClasses = 'bg-amber-700 border-b border-amber-600';
    let iconClasses = 'text-amber-200';
    let titleText = '⚠ WEAPON DETECTED';

    if (isFace) {
        containerClasses = 'bg-orange-700 border-b border-orange-600';
        iconClasses = 'text-orange-200';
        titleText = '⚠ SEVERE: TARGET RECOGNIZED';
    } else if (isCombined) {
        containerClasses = 'bg-red-700 border-b border-red-600';
        iconClasses = 'text-red-200 animate-pulse';
        titleText = '⚠ HIGHLY SEVERE: ARMED SUSPECT';
    }

    return (
        <div
            className={`fixed top-0 inset-x-0 z-[9999] transition-all duration-300
                ${visible ? 'translate-y-0 opacity-100' : '-translate-y-full opacity-0'}`}
        >
            <div className={`w-full px-6 py-3 flex items-center gap-4 ${containerClasses}`}>
                {/* Progress bar */}
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-white/20">
                    <div
                        className="h-full bg-white/60 transition-none"
                        style={{ width: `${progress}%` }}
                    />
                </div>

                <AlertTriangle className={`shrink-0 w-5 h-5 ${iconClasses}`} />

                <div className="flex-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-white">
                    <span className="font-bold">{titleText}</span>

                    <span className="flex items-center gap-1.5 opacity-90">
                        <Camera className="w-3.5 h-3.5" />
                        {alert.camera_id.replace(/_/g, ' ')}
                    </span>

                    {alert.identities?.length > 0 && (
                        <span className="flex items-center gap-1.5 font-semibold">
                            <User className="w-3.5 h-3.5" />
                            {alert.identities.join(', ')}
                        </span>
                    )}

                    <span className="opacity-60 text-xs">
                        {new Date(alert.timestamp).toLocaleTimeString()}
                    </span>
                </div>

                <button
                    onClick={handleDismiss}
                    className="shrink-0 text-white/60 hover:text-white transition-colors"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
}
