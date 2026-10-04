import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Server, Database, ShieldAlert, Cpu, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';

export default function SettingsPage() {
  const [healthData, setHealthData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  async function checkApi() {
    setIsLoading(true);
    setError('');
    try {
      const data = await api.checkHealth();
      setHealthData(data);
    } catch (err) {
      setError(err.message || 'Cannot connect to backend server.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    checkApi();
  }, []);

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">System Configuration & Settings</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Backend connection, provider status, and environment parameters.
          </p>
        </div>
        <button
          onClick={checkApi}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors shadow-2xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Check Status</span>
        </button>
      </div>

      {/* Backend Health Card */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Server className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
            FastAPI Backend Service
          </h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <span className="text-slate-400 block mb-0.5">API Base Endpoint</span>
            <span className="font-mono text-slate-800 font-medium bg-slate-50 p-1.5 rounded border border-slate-200 block truncate">
              {api.getBaseUrl()}
            </span>
          </div>

          <div>
            <span className="text-slate-400 block mb-0.5">Connectivity Status</span>
            <div className="flex items-center gap-1.5 pt-1">
              {healthData?.status === 'ok' ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span className="font-semibold text-emerald-700">Online & Responsive (v{healthData.version})</span>
                </>
              ) : (
                <>
                  <XCircle className="w-4 h-4 text-rose-600" />
                  <span className="font-semibold text-rose-700">{error || 'Disconnected'}</span>
                </>
              )}
            </div>
          </div>

          <div>
            <span className="text-slate-400 block mb-0.5">Database Connection</span>
            <div className="flex items-center gap-1.5 font-mono text-slate-800">
              <Database className="w-3.5 h-3.5 text-slate-400" />
              <span>SQLite ({healthData?.database || 'disconnected'})</span>
            </div>
          </div>

          <div>
            <span className="text-slate-400 block mb-0.5">Application Environment</span>
            <span className="text-slate-800 capitalize font-medium">{healthData?.environment || 'development'}</span>
          </div>
        </div>
      </div>

      {/* Pipeline Providers Card */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Cpu className="w-4 h-4 text-teal-600" />
          <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
            Service Provider Configuration
          </h3>
        </div>

        <div className="space-y-3 text-xs">
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded border border-slate-200/70">
            <div>
              <span className="font-semibold text-slate-900 block">Speech-to-Text Transcription</span>
              <span className="text-slate-500">Generates timestamped dialogue transcripts.</span>
            </div>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-blue-50 text-blue-700 border border-blue-200">
              Configurable: Gemini (gemini-3.5-transcribe) / Mock
            </span>
          </div>

          <div className="flex items-center justify-between p-3 bg-slate-50 rounded border border-slate-200/70">
            <div>
              <span className="font-semibold text-slate-900 block">Workflow Extraction</span>
              <span className="text-slate-500">Detects commitments, tasks, decisions, and open questions.</span>
            </div>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-teal-50 text-teal-700 border border-teal-200">
              Configurable: Gemma AI / Mock
            </span>
          </div>

          <div className="flex items-center justify-between p-3 bg-slate-50 rounded border border-slate-200/70">
            <div>
              <span className="font-semibold text-slate-900 block">Workflow Mock Executor</span>
              <span className="text-slate-500">Simulates task queueing and email delivery.</span>
            </div>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
              Mock Execution Service (In-Memory)
            </span>
          </div>
        </div>
      </div>

      {/* Security & Deployment Notice */}
      <div className="bg-amber-50/60 border border-amber-200 rounded-lg p-4 flex items-start gap-3 text-xs text-amber-900">
        <ShieldAlert className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-semibold block">Local Development Environment Notice</span>
          <p className="text-amber-800 leading-relaxed">
            MeetFlow is operating in local development mode without authentication or role-based access control.
            Endpoints are intended strictly for local development, testing, and demonstrations on a single server worker.
            Do not expose this server to the public internet without an authentication layer.
          </p>
        </div>
      </div>
    </div>
  );
}
