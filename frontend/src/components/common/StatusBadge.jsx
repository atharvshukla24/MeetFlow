import React from 'react';

const STATUS_CONFIGS = {
  // Meeting statuses
  uploaded: { label: 'Uploaded', bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-200' },
  transcribing: { label: 'Transcribing', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', pulse: true },
  transcribed: { label: 'Transcribed', bg: 'bg-teal-50', text: 'text-teal-700', border: 'border-teal-200' },
  transcription_failed: { label: 'Transcription Failed', bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
  analyzing: { label: 'Analyzing', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', pulse: true },
  analyzed: { label: 'Analyzed', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  analysis_failed: { label: 'Analysis Failed', bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },

  // Action statuses
  pending: { label: 'Pending Approval', bg: 'bg-amber-50', text: 'text-amber-800', border: 'border-amber-200' },
  edited: { label: 'Edited', bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
  approved: { label: 'Approved', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  rejected: { label: 'Rejected', bg: 'bg-slate-100', text: 'text-slate-600', border: 'border-slate-300' },
  executing: { label: 'Executing', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', pulse: true },
  succeeded: { label: 'Executed', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  failed: { label: 'Execution Failed', bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
  needs_clarification: { label: 'Needs Clarification', bg: 'bg-amber-100', text: 'text-amber-900', border: 'border-amber-300' },

  // Action types
  task: { label: 'Task', bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200' },
  email: { label: 'Email Draft', bg: 'bg-violet-50', text: 'text-violet-700', border: 'border-violet-200' },
  reminder: { label: 'Reminder', bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  calendar_event: { label: 'Calendar', bg: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-200' },
  message: { label: 'Message', bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-200' },
};

export default function StatusBadge({ status, type = 'status', className = '' }) {
  const key = (status || '').toLowerCase();
  const config = STATUS_CONFIGS[key] || {
    label: status || 'Unknown',
    bg: 'bg-slate-100',
    text: 'text-slate-700',
    border: 'border-slate-200',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-medium border ${config.bg} ${config.text} ${config.border} ${className}`}
    >
      {config.pulse && (
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping inline-block" />
      )}
      {config.label}
    </span>
  );
}
