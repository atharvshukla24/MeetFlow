import React from 'react';
import { Link } from 'react-router-dom';
import StatusBadge from '../common/StatusBadge';
import { ArrowRight, FileAudio, Calendar } from 'lucide-react';

export default function MeetingList({ meetings }) {
  function formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-600">
          <thead className="bg-slate-50/75 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            <tr>
              <th className="py-3 px-4">Meeting Title</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Recording</th>
              <th className="py-3 px-4">Uploaded Date</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {meetings.map((meeting) => (
              <tr key={meeting.id} className="hover:bg-slate-50/80 transition-colors">
                <td className="py-3.5 px-4 font-medium text-slate-900">
                  <Link
                    to={`/meetings/${meeting.id}`}
                    className="hover:text-blue-600 hover:underline flex items-center gap-1.5"
                  >
                    <span>{meeting.title || 'Untitled Meeting'}</span>
                  </Link>
                  <span className="text-[10px] text-slate-400 block font-normal font-mono mt-0.5">
                    ID: {meeting.id.substring(0, 8)}...
                  </span>
                </td>
                <td className="py-3.5 px-4">
                  <StatusBadge status={meeting.status} />
                </td>
                <td className="py-3.5 px-4">
                  <div className="flex items-center gap-1.5 text-slate-600 font-mono text-[11px]">
                    <FileAudio className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span className="truncate max-w-[180px]">{meeting.audio_filename || '—'}</span>
                  </div>
                </td>
                <td className="py-3.5 px-4 text-slate-500">
                  <div className="flex items-center gap-1.5 text-[11px]">
                    <Calendar className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span>{formatDate(meeting.created_at)}</span>
                  </div>
                </td>
                <td className="py-3.5 px-4 text-right">
                  <Link
                    to={`/meetings/${meeting.id}`}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 hover:text-blue-600 transition-colors shadow-2xs"
                  >
                    <span>View</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
