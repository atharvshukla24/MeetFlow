import React, { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { api } from '../../services/api';
import { ChevronRight } from 'lucide-react';

export default function TopBar() {
  const location = useLocation();
  const [backendStatus, setBackendStatus] = useState({ connected: false, version: '', loading: true });

  useEffect(() => {
    let isMounted = true;
    async function verifyHealth() {
      try {
        const data = await api.checkHealth();
        if (isMounted) {
          setBackendStatus({ connected: true, version: data.version || '0.1.0', loading: false });
        }
      } catch {
        if (isMounted) {
          setBackendStatus({ connected: false, version: '', loading: false });
        }
      }
    }
    verifyHealth();
    const interval = setInterval(verifyHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Compute breadcrumbs
  const pathParts = location.pathname.split('/').filter(Boolean);

  return (
    <header className="h-14 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0">
      {/* Breadcrumb / Location */}
      <div className="flex items-center gap-1.5 text-xs text-slate-500">
        <Link to="/" className="hover:text-slate-900 transition-colors">
          MeetFlow
        </Link>
        {pathParts.length > 0 ? (
          pathParts.map((part, index) => {
            const isLast = index === pathParts.length - 1;
            const label = part === 'actions' ? 'Actions' : part === 'settings' ? 'Settings' : part;
            return (
              <React.Fragment key={part}>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                <span className={isLast ? 'font-medium text-slate-800' : 'hover:text-slate-900'}>
                  {label}
                </span>
              </React.Fragment>
            );
          })
        ) : (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            <span className="font-medium text-slate-800">Meetings</span>
          </>
        )}
      </div>

      {/* Backend Connectivity Status Pill */}
      <div className="flex items-center gap-2">
        <div
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
            backendStatus.connected
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-rose-50 text-rose-700 border-rose-200'
          }`}
          title={backendStatus.connected ? `FastAPI connected (v${backendStatus.version})` : 'Backend unreachable on port 8000'}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              backendStatus.connected ? 'bg-emerald-500' : 'bg-rose-500'
            }`}
          />
          <span>{backendStatus.connected ? `API v${backendStatus.version}` : 'API Offline'}</span>
        </div>
      </div>
    </header>
  );
}
