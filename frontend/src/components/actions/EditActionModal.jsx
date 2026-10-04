import React, { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import { api } from '../../services/api';
import { AlertCircle, Loader2 } from 'lucide-react';

export default function EditActionModal({ isOpen, onClose, action, onActionUpdated }) {
  const [description, setDescription] = useState('');
  const [owner, setOwner] = useState('');
  const [deadlineText, setDeadlineText] = useState('');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [draftSubject, setDraftSubject] = useState('');
  const [draftBody, setDraftBody] = useState('');
  const [resolveClarification, setResolveClarification] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (action) {
      setDescription(action.description || '');
      setOwner(action.owner || '');
      setDeadlineText(action.deadline_text || '');
      setRecipientEmail(action.recipient_email || '');
      setDraftSubject(action.draft_subject || '');
      setDraftBody(action.draft_body || '');
      setResolveClarification(false);
      setError('');
    }
  }, [action]);

  if (!action) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    // Pre-flight validation if attempting to clear clarification
    if (resolveClarification) {
      if (action.type === 'task' && !owner.trim()) {
        setError("Cannot clear clarification for task: 'owner' is required.");
        return;
      }
      if (action.type === 'email' && (!recipientEmail.trim() || !recipientEmail.includes('@'))) {
        setError("Cannot clear clarification for email: valid 'recipient_email' is required.");
        return;
      }
      if ((action.type === 'reminder' || action.type === 'calendar_event') && !deadlineText.trim()) {
        setError(`Cannot clear clarification for ${action.type}: 'deadline_text' is required.`);
        return;
      }
    }

    setIsSaving(true);

    try {
      const payload = {
        description: description.trim(),
        owner: owner.trim() || null,
        deadline_text: deadlineText.trim() || null,
      };

      if (action.type === 'email') {
        payload.recipient_email = recipientEmail.trim() || null;
        payload.draft_subject = draftSubject.trim() || null;
        payload.draft_body = draftBody.trim() || null;
      }

      if (resolveClarification) {
        payload.needs_clarification = false;
      }

      const updated = await api.updateAction(action.id, payload);
      onActionUpdated(updated);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to update action.');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Edit Action Item"
      subtitle={`Type: ${action.type?.toUpperCase()} • Status: ${action.approval_status}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 rounded-md bg-rose-50 border border-rose-200 flex items-start gap-2 text-xs text-rose-700">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="flex-1">{error}</div>
          </div>
        )}

        {action.approval_status === 'approved' && (
          <div className="p-2.5 rounded bg-blue-50 border border-blue-200 text-xs text-blue-800">
            <strong>Note:</strong> Editing an approved action will revoke approval and reset its status to <em>Edited</em>, requiring re-approval before execution.
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">
            Description <span className="text-rose-500">*</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            rows={2}
            className="w-full px-3 py-2 text-xs rounded border border-slate-300 focus:outline-hidden focus:border-blue-600 focus:ring-1 focus:ring-blue-600 bg-white"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Assigned Owner {action.type === 'task' && <span className="text-slate-400 font-normal">(required for tasks)</span>}
            </label>
            <input
              type="text"
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="e.g. Alice"
              className="w-full px-3 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:border-blue-600 focus:ring-1 focus:ring-blue-600 bg-white"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Deadline / Target Date
            </label>
            <input
              type="text"
              value={deadlineText}
              onChange={(e) => setDeadlineText(e.target.value)}
              placeholder="e.g. by Wednesday"
              className="w-full px-3 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:border-blue-600 focus:ring-1 focus:ring-blue-600 bg-white"
            />
          </div>
        </div>

        {action.type === 'email' && (
          <div className="space-y-3 pt-2 border-t border-slate-100">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Recipient Email <span className="text-rose-500">*</span>
              </label>
              <input
                type="email"
                value={recipientEmail}
                onChange={(e) => setRecipientEmail(e.target.value)}
                placeholder="colleague@example.com"
                className="w-full px-3 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:border-blue-600 focus:ring-1 focus:ring-blue-600 bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Draft Subject
              </label>
              <input
                type="text"
                value={draftSubject}
                onChange={(e) => setDraftSubject(e.target.value)}
                placeholder="e.g. Sprint Summary"
                className="w-full px-3 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:border-blue-600 focus:ring-1 focus:ring-blue-600 bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Draft Body
              </label>
              <textarea
                value={draftBody}
                onChange={(e) => setDraftBody(e.target.value)}
                rows={3}
                placeholder="Draft message contents..."
                className="w-full px-3 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:border-blue-600 focus:ring-1 focus:ring-blue-600 bg-white"
              />
            </div>
          </div>
        )}

        {action.needs_clarification && (
          <div className="p-3 bg-amber-50/70 border border-amber-200 rounded text-xs text-amber-900 space-y-2">
            <span className="font-semibold block">Clarification Required</span>
            <label className="flex items-center gap-2 cursor-pointer font-medium">
              <input
                type="checkbox"
                checked={resolveClarification}
                onChange={(e) => setResolveClarification(e.target.checked)}
                className="rounded border-amber-400 text-blue-600 focus:ring-blue-500"
              />
              <span>Mark clarification as resolved (required fields supplied above)</span>
            </label>
          </div>
        )}

        <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="px-3.5 py-1.5 rounded text-xs font-medium text-slate-700 hover:bg-slate-100 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-xs"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <span>Save Action</span>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
