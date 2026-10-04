import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import MeetingList from '../components/meetings/MeetingList';
import UploadModal from '../components/meetings/UploadModal';
import EmptyState from '../components/common/EmptyState';
import { Plus, Video, AlertCircle, RefreshCw, Loader2 } from 'lucide-react';

export default function MeetingsPage() {
  const navigate = useNavigate();
  const [meetings, setMeetings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  async function loadMeetings() {
    setIsLoading(true);
    setError('');
    try {
      const data = await api.listMeetings();
      setMeetings(data || []);
    } catch (err) {
      setError(err.message || 'Failed to load meetings list.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadMeetings();
  }, []);

  function handleUploadSuccess(createdMeeting) {
    setIsUploadOpen(false);
    // Navigate straight to the created meeting details
    if (createdMeeting && createdMeeting.id) {
      navigate(`/meetings/${createdMeeting.id}`);
    } else {
      loadMeetings();
    }
  }

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Meetings</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Recorded meetings, transcripts, and extracted workflow items.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadMeetings}
            disabled={isLoading}
            className="p-1.5 text-slate-600 bg-white border border-slate-200 rounded hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-2xs"
            title="Refresh meetings"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setIsUploadOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-colors shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Upload Recording</span>
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg flex items-start justify-between gap-3 text-xs text-rose-800">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block">Failed to load meetings</span>
              <span>{error}</span>
            </div>
          </div>
          <button
            onClick={loadMeetings}
            className="px-2.5 py-1 text-xs font-medium text-rose-700 bg-white border border-rose-200 rounded hover:bg-rose-50 transition-colors shadow-2xs"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-blue-600 mb-2" />
          <span>Loading meetings from server...</span>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && meetings.length === 0 && (
        <EmptyState
          icon={Video}
          title="No meetings uploaded yet"
          description="Upload an audio recording of your meeting to transcribe it, extract action items, and execute approved workflows."
          actionText="Upload Recording"
          onAction={() => setIsUploadOpen(true)}
        />
      )}

      {/* Populated List */}
      {!isLoading && !error && meetings.length > 0 && (
        <MeetingList meetings={meetings} />
      )}

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
}
