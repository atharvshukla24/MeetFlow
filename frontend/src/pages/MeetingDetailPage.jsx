import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';
import OverviewTab from '../components/meetings/OverviewTab';
import TranscriptTab from '../components/meetings/TranscriptTab';
import ActionsTab from '../components/meetings/ActionsTab';
import StatusBadge from '../components/common/StatusBadge';
import { ArrowLeft, Loader2, AlertCircle, RefreshCw } from 'lucide-react';

export default function MeetingDetailPage() {
  const { id } = useParams();
  const [meeting, setMeeting] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');

  async function loadMeeting() {
    setIsLoading(true);
    setError('');
    try {
      const data = await api.getMeeting(id);
      setMeeting(data);
    } catch (err) {
      setError(err.message || 'Failed to load meeting details.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadMeeting();
  }, [id]);

  async function handleTranscribe() {
    setIsProcessing(true);
    setActionError('');
    try {
      await api.transcribeMeeting(id);
      // Reload full meeting
      const refreshed = await api.getMeeting(id);
      setMeeting(refreshed);
      setActiveTab('transcript');
    } catch (err) {
      setActionError(err.message || 'Transcription failed.');
      // Refresh to update status if failed
      try {
        const refreshed = await api.getMeeting(id);
        setMeeting(refreshed);
      } catch {}
    } finally {
      setIsProcessing(false);
    }
  }

  async function handleAnalyze() {
    setIsProcessing(true);
    setActionError('');
    try {
      await api.analyzeMeeting(id);
      const refreshed = await api.getMeeting(id);
      setMeeting(refreshed);
      setActiveTab('actions');
    } catch (err) {
      setActionError(err.message || 'Workflow extraction failed.');
      try {
        const refreshed = await api.getMeeting(id);
        setMeeting(refreshed);
      } catch {}
    } finally {
      setIsProcessing(false);
    }
  }

  function handleTranscriptUpdated(newTranscript) {
    setMeeting((prev) => (prev ? { ...prev, transcript: newTranscript } : prev));
  }

  function handleActionChanged(updatedAction) {
    setMeeting((prev) => {
      if (!prev) return prev;
      const updatedActions = (prev.actions || []).map((a) =>
        a.id === updatedAction.id ? updatedAction : a
      );
      return { ...prev, actions: updatedActions };
    });
  }

  if (isLoading) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600 mb-2" />
        <span>Loading meeting details...</span>
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div className="space-y-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Meetings</span>
        </Link>
        <div className="p-6 bg-white border border-rose-200 rounded-lg text-center space-y-3">
          <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
          <h2 className="text-base font-semibold text-slate-900">Meeting Not Found</h2>
          <p className="text-xs text-slate-500 max-w-md mx-auto">{error || 'Unable to retrieve meeting data.'}</p>
          <button
            onClick={loadMeeting}
            className="px-3.5 py-1.5 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors shadow-xs"
          >
            Retry Loading
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Navigation & Title */}
      <div>
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900 transition-colors mb-2"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>All Meetings</span>
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              {meeting.title || 'Untitled Meeting'}
            </h1>
            <StatusBadge status={meeting.status} />
          </div>

          <button
            onClick={loadMeeting}
            disabled={isProcessing}
            className="self-start sm:self-auto p-1.5 text-slate-600 bg-white border border-slate-200 rounded hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-2xs"
            title="Refresh meeting"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {actionError && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-md text-xs text-rose-800 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <div className="flex-1">{actionError}</div>
        </div>
      )}

      {/* Tabs navigation */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-6 text-xs font-medium">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-2.5 border-b-2 transition-colors ${
              activeTab === 'overview'
                ? 'border-blue-600 text-blue-600 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('transcript')}
            className={`py-2.5 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'transcript'
                ? 'border-blue-600 text-blue-600 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <span>Transcript</span>
            {meeting.transcript && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
            )}
          </button>
          <button
            onClick={() => setActiveTab('actions')}
            className={`py-2.5 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'actions'
                ? 'border-blue-600 text-blue-600 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <span>Actions & Decisions</span>
            {meeting.actions?.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-blue-100 text-blue-800 font-semibold">
                {meeting.actions.length}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* Tab Panels */}
      {activeTab === 'overview' && (
        <OverviewTab
          meeting={meeting}
          onTranscribe={handleTranscribe}
          onAnalyze={handleAnalyze}
          isProcessing={isProcessing}
          setActiveTab={setActiveTab}
        />
      )}

      {activeTab === 'transcript' && (
        <TranscriptTab
          meeting={meeting}
          onTranscriptUpdated={handleTranscriptUpdated}
          onTranscribe={handleTranscribe}
          isProcessing={isProcessing}
          actionError={actionError}
        />
      )}

      {activeTab === 'actions' && (
        <ActionsTab
          meeting={meeting}
          onActionChanged={handleActionChanged}
        />
      )}
    </div>
  );
}
