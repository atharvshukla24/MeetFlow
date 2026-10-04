import React from 'react';
import StatusBadge from '../common/StatusBadge';
import { Play, Sparkles, CheckCircle2, AlertCircle, Loader2, ArrowRight, FileText, CheckSquare, HelpCircle } from 'lucide-react';

export default function OverviewTab({
  meeting,
  onTranscribe,
  onAnalyze,
  isProcessing,
  setActiveTab,
}) {
  function formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  }

  const actionsCount = meeting.actions?.length || 0;
  const decisionsCount = meeting.decisions?.length || 0;
  const questionsCount = meeting.open_questions?.length || 0;

  return (
    <div className="space-y-6">
      {/* Primary Action Card based on Meeting Status */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Workflow Pipeline Status
        </h3>

        {meeting.status === 'uploaded' && (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-md bg-blue-50/60 border border-blue-100">
            <div>
              <h4 className="text-sm font-semibold text-slate-900">Audio Ready for Transcription</h4>
              <p className="text-xs text-slate-600 mt-0.5">
                Generate timestamped dialogue transcript from your uploaded audio recording.
              </p>
            </div>
            <button
              onClick={onTranscribe}
              disabled={isProcessing}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-xs shrink-0"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Transcribing...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Transcribe Recording</span>
                </>
              )}
            </button>
          </div>
        )}

        {meeting.status === 'transcribing' && (
          <div className="flex items-center gap-3 p-4 rounded-md bg-blue-50/80 border border-blue-200 text-blue-900 text-xs">
            <Loader2 className="w-4 h-4 animate-spin text-blue-600 shrink-0" />
            <div>
              <span className="font-semibold block">Transcription in Progress</span>
              <span className="text-blue-700">Transcribing audio recording into timestamped dialogue...</span>
            </div>
          </div>
        )}

        {meeting.status === 'transcription_failed' && (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-md bg-rose-50 border border-rose-200 text-xs">
            <div className="flex items-start gap-2 text-rose-800">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block">Transcription Failed</span>
                <span className="text-rose-700">The transcription process encountered an error. You can retry safely.</span>
              </div>
            </div>
            <button
              onClick={onTranscribe}
              disabled={isProcessing}
              className="px-3.5 py-1.5 rounded-md text-xs font-medium text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-50 transition-colors shadow-xs shrink-0"
            >
              Retry Transcription
            </button>
          </div>
        )}

        {meeting.status === 'transcribed' && (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-md bg-emerald-50/60 border border-emerald-200">
            <div>
              <div className="flex items-center gap-1.5 text-emerald-800 font-semibold text-sm">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Transcript Ready</span>
              </div>
              <p className="text-xs text-slate-600 mt-0.5">
                Analyze transcript text to extract structured tasks, explicit decisions, and open questions.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab('transcript')}
                className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors"
              >
                Review Transcript
              </button>
              {meeting.is_mock && (
                <button
                  onClick={onTranscribe}
                  disabled={isProcessing}
                  className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors"
                  title="Re-run transcription with Gemini"
                >
                  Transcribe with Gemini
                </button>
              )}
              <button
                onClick={onAnalyze}
                disabled={isProcessing}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-xs shrink-0"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Extract Workflow</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {meeting.status === 'analyzing' && (
          <div className="flex items-center gap-3 p-4 rounded-md bg-blue-50/80 border border-blue-200 text-blue-900 text-xs">
            <Loader2 className="w-4 h-4 animate-spin text-blue-600 shrink-0" />
            <div>
              <span className="font-semibold block">Workflow Extraction in Progress</span>
              <span className="text-blue-700">Parsing dialogue commitments, decisions, and unresolved questions.</span>
            </div>
          </div>
        )}

        {meeting.status === 'analysis_failed' && (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-md bg-rose-50 border border-rose-200 text-xs">
            <div className="flex items-start gap-2 text-rose-800">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block">Workflow Analysis Failed</span>
                <span className="text-rose-700">Internal error during extraction. Previous workflow remains preserved.</span>
              </div>
            </div>
            <button
              onClick={onAnalyze}
              disabled={isProcessing}
              className="px-3.5 py-1.5 rounded-md text-xs font-medium text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-50 transition-colors shadow-xs shrink-0"
            >
              Retry Analysis
            </button>
          </div>
        )}

        {meeting.status === 'analyzed' && (
          <div className="space-y-4">
            <div className="p-4 rounded-md bg-slate-50 border border-slate-200">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-slate-700">Meeting Executive Summary</span>
                {meeting.extraction_provider === 'gemma' ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                    Gemma AI
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-100 text-slate-600 border border-slate-200">
                    Historical Mock Data
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-800 leading-relaxed">
                {meeting.summary || 'Summary generated from transcript analysis.'}
              </p>
            </div>

            {/* Metrics cards */}
            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => setActiveTab('actions')}
                className="p-3 bg-white border border-slate-200 rounded text-left hover:border-blue-400 hover:bg-blue-50/20 transition-colors group"
              >
                <div className="flex items-center justify-between text-slate-500 mb-1">
                  <span className="text-xs font-medium">Action Items</span>
                  <CheckSquare className="w-4 h-4 text-blue-600" />
                </div>
                <div className="text-xl font-bold text-slate-900">{actionsCount}</div>
                <span className="text-[11px] text-blue-600 group-hover:underline inline-flex items-center gap-0.5 mt-1">
                  Review & Approve <ArrowRight className="w-2.5 h-2.5" />
                </span>
              </button>

              <button
                onClick={() => setActiveTab('actions')}
                className="p-3 bg-white border border-slate-200 rounded text-left hover:border-teal-400 hover:bg-teal-50/20 transition-colors group"
              >
                <div className="flex items-center justify-between text-slate-500 mb-1">
                  <span className="text-xs font-medium">Decisions</span>
                  <CheckCircle2 className="w-4 h-4 text-teal-600" />
                </div>
                <div className="text-xl font-bold text-slate-900">{decisionsCount}</div>
                <span className="text-[11px] text-teal-700 group-hover:underline inline-flex items-center gap-0.5 mt-1">
                  View Decisions <ArrowRight className="w-2.5 h-2.5" />
                </span>
              </button>

              <button
                onClick={() => setActiveTab('actions')}
                className="p-3 bg-white border border-slate-200 rounded text-left hover:border-amber-400 hover:bg-amber-50/20 transition-colors group"
              >
                <div className="flex items-center justify-between text-slate-500 mb-1">
                  <span className="text-xs font-medium">Open Questions</span>
                  <HelpCircle className="w-4 h-4 text-amber-600" />
                </div>
                <div className="text-xl font-bold text-slate-900">{questionsCount}</div>
                <span className="text-[11px] text-amber-800 group-hover:underline inline-flex items-center gap-0.5 mt-1">
                  View Questions <ArrowRight className="w-2.5 h-2.5" />
                </span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Metadata Specification Table */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Meeting File & System Details
        </h3>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-xs">
          <div>
            <dt className="text-slate-400">Meeting ID</dt>
            <dd className="font-mono text-slate-800 font-medium break-all">{meeting.id}</dd>
          </div>
          <div>
            <dt className="text-slate-400">Current Status</dt>
            <dd className="mt-0.5">
              <StatusBadge status={meeting.status} />
            </dd>
          </div>
          <div>
            <dt className="text-slate-400">Audio Recording Filename</dt>
            <dd className="font-mono text-slate-800 font-medium">{meeting.audio_filename || '—'}</dd>
          </div>
          <div>
            <dt className="text-slate-400">Created Date</dt>
            <dd className="text-slate-800">{formatDate(meeting.created_at)}</dd>
          </div>
          <div>
            <dt className="text-slate-400">Last Updated</dt>
            <dd className="text-slate-800">{formatDate(meeting.updated_at)}</dd>
          </div>
          <div>
            <dt className="text-slate-400">Transcription Provider</dt>
            <dd className="text-slate-800 font-medium">
              {meeting.transcription_provider === 'gemini'
                ? 'Gemini Transcribe (gemini-3.5-transcribe)'
                : meeting.transcription_provider === 'mock'
                ? 'Historical Mock Provider'
                : 'Not Transcribed Yet'}
            </dd>
          </div>
          <div>
            <dt className="text-slate-400">Extraction Provider</dt>
            <dd className="text-slate-800 font-medium">
              {meeting.extraction_provider === 'gemma'
                ? 'Gemma AI (Google GenAI API)'
                : meeting.extraction_provider === 'mock'
                ? 'Historical Mock Provider'
                : 'Not Analyzed Yet'}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
