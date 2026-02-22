import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { KeyRound, Loader2, ShieldCheck } from 'lucide-react';
import authRequest, { setAccessToken, setRefreshToken } from '../utils/authRequest';
import { useAuth } from '../contexts/AuthContext';

const FASTAPI_URL = import.meta.env.VITE_BACKEND_URL as string; // Desktop FastAPI

export default function VerifyOTP() {
    const navigate = useNavigate();
    const location = useLocation();
    const { checkAuth } = useAuth();
    const email = location.state?.email as string | undefined;

    const [otp, setOtp] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    if (!email) {
        navigate('/login', { replace: true });
        return null;
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);
        try {
            // Step 1: Verify OTP with Django (Desktop endpoint — returns tokens in body, no cookie)
            const data = await authRequest.post('/auth/desktop/verify-otp/', { email, otp });

            if (data.access) {
                // Step 2: Store tokens — access in memory + localStorage, refresh in localStorage
                setAccessToken(data.access);
                if (data.refresh) setRefreshToken(data.refresh);

                // Step 3: Register this Desktop Client node in Django via local FastAPI
                try {
                    await fetch(`${FASTAPI_URL}/node/register`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ access_token: data.access }),
                    });
                } catch (nodeErr) {
                    // Non-fatal — node registration failure shouldn't block login
                    console.warn('Node registration failed:', nodeErr);
                }

                // Step 4: Update auth context → triggers re-route to Home
                await checkAuth();
                navigate('/', { replace: true });
            } else {
                setError('Unexpected server response.');
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Verification failed. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                <div className="text-center mb-8">
                    <div className="flex justify-center mb-4">
                        <div className="w-16 h-16 bg-blue-600/20 rounded-2xl flex items-center justify-center border border-blue-500/30">
                            <ShieldCheck className="w-8 h-8 text-blue-400" />
                        </div>
                    </div>
                    <h1 className="text-2xl font-bold text-white">Two-Factor Authentication</h1>
                    <p className="text-gray-400 mt-1 text-sm">
                        Enter the code sent to <span className="text-blue-400 font-medium">{email}</span>
                    </p>
                </div>

                <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-xl p-8">
                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1.5">Verification Code</label>
                            <div className="relative">
                                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                                <input
                                    type="text"
                                    value={otp}
                                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                    placeholder="######"
                                    maxLength={6}
                                    required
                                    className="w-full bg-gray-700/60 border border-gray-600 rounded-lg pl-10 pr-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition tracking-widest text-lg font-mono"
                                />
                            </div>
                        </div>

                        {error && (
                            <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                                {error}
                            </p>
                        )}

                        <button
                            type="submit"
                            disabled={isLoading || otp.length < 6}
                            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg transition-colors"
                        >
                            {isLoading ? (
                                <><Loader2 className="w-4 h-4 animate-spin" /> Verifying...</>
                            ) : (
                                'Verify Code'
                            )}
                        </button>

                        <button
                            type="button"
                            onClick={() => navigate('/login')}
                            className="w-full text-sm text-gray-500 hover:text-gray-300 transition-colors pt-1"
                        >
                            ← Back to Login
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
