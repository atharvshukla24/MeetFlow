import React, { useState } from 'react';
import { api } from '../../services/api';
import { Edit3, Check, AlertTriangle, AlertCircle, Loader2, Play, FileText } from 'lucide-react';

const SYNTHETIC_BANNER = '[SYNTHETIC SAMPLE TRANSCRIPT — DEMO ONLY]';

export default function TranscriptTab({
  meeting,
  onTranscriptUpdated,
  onTranscribe,
  isProcessing,
  actionError,
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(meeting.transcript || '');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const isMock = Boolean(
    meeting.is_mock ||
    meeting.transcription_provider === 'mock' ||
    meeting.transcript?.includes(SYNTHETIC_BANNER)
  );

  function startEdit() {
    setEditText(meeting.transcript || '');
    setError('');
    setIsEditing(true);
  }

  function cancelEdit() {
    setEditText(meeting.transcript || '');
    setError('');
    setIsEditing(false);
  }

  async function handleSave() {
    if (!editText.trim()) {
      setError('Transcript cannot be empty.');
      return;
    }

    setIsSaving(true);
    setError('');

    try {
      const updated = await api.updateTranscript(meeting.id, editText);
      setIsEditing(false);
      onTranscriptUpdated(updated.transcript);
    } catch (err) {
      setError(err.message || 'Failed to save transcript update.');
    } finally {
      setIsSaving(false);
    }
  }

  // 1. Processing state
  if (meeting.status === 'transcribing' || (isProcessing && !meeting.transcript)) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-slate-600 flex flex-col items-center justify-center space-y-3 shadow-xs">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        <div>
          <h4 className="text-sm font-semibold text-slate-900">Transcription in Progress</h4>
          <p className="text-xs text-slate-500 mt-1">
            Sending audio to Google Gemini API (gemini-3.5-transcribe)...
          </p>
        </div>
      </div>
    );
  }

  // 2. Transcription Failed state
  if (meeting.status === 'transcription_failed' && !meeting.transcript) {
    return (
      <div className="bg-white border border-rose-200 rounded-lg p-8 text-center space-y-4 shadow-xs">
        <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
        <div>
          <h4 className="text-sm font-semibold text-slate-900">Transcription Failed</h4>
          <p className="text-xs text-rose-700 mt-1 max-w-md mx-auto">
            {actionError || 'The transcription request encountered an error. The uploaded audio is preserved and ready for retry.'}
          </p>
        </div>
        {onTranscribe && (
          <button
            onClick={onTranscribe}
            disabled={isProcessing}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-50 rounded transition-colors shadow-xs"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Retrying...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Retry Transcription</span>
              </>
            )}
          </button>
        )}
      </div>
    );
  }

  // 3. No transcript yet state
  if (!meeting.transcript) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-10 text-center space-y-4 shadow-xs">
        <FileText className="w-10 h-10 text-slate-300 mx-auto" />
        <div>
          <h4 className="text-sm font-semibold text-slate-900">No transcript yet</h4>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            This meeting has not been transcribed yet. Start transcription to process the uploaded recording with Gemini.
          </p>
        </div>
        {onTranscribe && (
          <button
            onClick={onTranscribe}
            disabled={isProcessing}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded transition-colors shadow-xs"
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
        )}
      </div>
    );
  }

  // 4. Success / View Transcript
  const lines = (meeting.transcript || '').split('\n').filter(Boolean);

  return (
    <div className="space-y-4">
      {/* Historical mock data indicator (only for old legacy mock records) */}
      {isMock && (
        <div className="bg-slate-50 border border-slate-200 rounded-md p-3 flex items-start gap-2.5 text-xs text-slate-700">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold block text-slate-900">Historical Mock Data</span>
            <span className="text-slate-600">
              This transcript was generated using a simulated provider in an earlier test. You can re-transcribe this recording from the Overview tab using Google Gemini.
            </span>
          </div>
        </div>
      )}

      {/* Transcript Card */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xs">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-700">Timestamped Dialogue</span>
            {meeting.transcription_provider === 'gemini' || (!isMock && meeting.transcript) ? (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-teal-50 text-teal-700 border border-teal-200">
                Gemini
              </span>
            ) : (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-100 text-slate-600 border border-slate-200">
                Historical Mock Data
              </span>
            )}
          </div>
          {!isEditing && (
            <button
              onClick={startEdit}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 hover:text-blue-600 transition-colors shadow-2xs"
            >
              <Edit3 className="w-3.5 h-3.5" />
              <span>Edit Transcript</span>
            </button>
          )}
        </div>

        {error && (
          <div className="p-3 bg-rose-50 border-b border-rose-200 text-xs text-rose-700">
            {error}
          </div>
        )}

        <div className="p-5">
          {isEditing ? (
            <div className="space-y-3">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                disabled={isSaving}
                rows={12}
                className="w-full p-3 font-mono text-xs rounded border border-slate-300 focus:outline-hidden focus:border-blue-600 focus:ring-1 focus:ring-blue-600 leading-relaxed bg-white"
              />
              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={cancelEdit}
                  disabled={isSaving}
                  className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={isSaving}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded transition-colors shadow-xs"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      <span>Save Changes</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-2.5 font-mono text-xs leading-relaxed text-slate-800">
              {lines.map((line, idx) => {
                if (line.includes(SYNTHETIC_BANNER)) return null;

                // Match [00:01:23] Speaker: text
                const match = line.match(/^(\[\d{2}:\d{2}:\d{2}\])\s*([^:]+):\s*(.*)$/);
                if (match) {
                  const [, timestamp, speaker, body] = match;
                  return (
                    <div key={idx} className="flex items-start gap-2.5 py-1 border-b border-slate-50 last:border-b-0">
                      <span className="text-[11px] text-slate-400 select-none shrink-0 font-normal">
                        {timestamp}
                      </span>
                      <span className="font-semibold text-blue-900 shrink-0 min-w-[70px]">
                        {speaker}:
                      </span>
                      <span className="text-slate-800 font-sans text-xs">{body}</span>
                    </div>
                  );
                }

                return (
                  <p key={idx} className="text-slate-700 font-sans text-xs">
                    {line}
                  </p>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
