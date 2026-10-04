import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import StatusBadge from '../components/common/StatusBadge';
import Modal from '../components/common/Modal';
import EditActionModal from '../components/actions/EditActionModal';
import EmptyState from '../components/common/EmptyState';
import { CheckSquare, Check, X, Play, Edit3, Eye, AlertCircle, Loader2, RefreshCw } from 'lucide-react';

const FILTER_TABS = [
  { key: 'all', label: 'All Actions' },
  { key: 'pending', label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'succeeded', label: 'Executed' },
  { key: 'needs_clarification', label: 'Needs Clarification' },
  { key: 'rejected', label: 'Rejected' },
];

export default function ActionsPage() {
  const [actions, setActions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [selectedActionForEdit, setSelectedActionForEdit] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);
  const [processingId, setProcessingId] = useState(null);

  async function loadActions() {
    setIsLoading(true);
    setError('');
    try {
      const data = await api.listActions();
      setActions(data || []);
    } catch (err) {
      setError(err.message || 'Failed to load actions.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadActions();
  }, []);

  async function handleApprove(actionId) {
    setProcessingId(actionId);
    try {
      const updated = await api.approveAction(actionId);
      setActions((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch (err) {
      alert(err.message || 'Failed to approve action.');
    } finally {
      setProcessingId(null);
    }
  }

  async function handleReject(actionId) {
    setProcessingId(actionId);
    try {
      const updated = await api.rejectAction(actionId);
      setActions((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch (err) {
      alert(err.message || 'Failed to reject action.');
    } finally {
      setProcessingId(null);
    }
  }

  async function handleExecute(actionId) {
    setProcessingId(actionId);
    try {
      const updated = await api.executeAction(actionId);
      setActions((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch (err) {
      alert(err.message || 'Failed to execute action.');
    } finally {
      setProcessingId(null);
    }
  }

  const filteredActions = actions.filter((act) => {
    if (activeFilter === 'all') return true;
    if (activeFilter === 'needs_clarification') return act.needs_clarification;
    return act.approval_status === activeFilter;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Extracted Actions</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Review, edit, approve, and execute tasks and communication drafts.
          </p>
        </div>
        <button
          onClick={loadActions}
          disabled={isLoading}
          className="self-start sm:self-auto p-1.5 text-slate-600 bg-white border border-slate-200 rounded hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-2xs"
          title="Refresh actions"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-1.5">
        {FILTER_TABS.map((tab) => {
          const count = actions.filter((a) =>
            tab.key === 'all'
              ? true
              : tab.key === 'needs_clarification'
              ? a.needs_clarification
              : a.approval_status === tab.key
          ).length;
          const isActive = activeFilter === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveFilter(tab.key)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors inline-flex items-center gap-1.5 ${
                isActive
                  ? 'bg-blue-600 text-white font-semibold shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                  isActive ? 'bg-blue-700 text-white' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg flex items-center justify-between text-xs text-rose-800">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={loadActions}
            className="px-2.5 py-1 text-xs font-medium text-rose-700 bg-white border border-rose-200 rounded hover:bg-rose-50 shadow-2xs"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-blue-600 mb-2" />
          <span>Loading actions...</span>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && filteredActions.length === 0 && (
        <EmptyState
          icon={CheckSquare}
          title="No actions found"
          description={
            activeFilter === 'all'
              ? 'No workflow actions have been extracted from meetings yet.'
              : `No actions currently match the '${activeFilter.replace('_', ' ')}' status filter.`
          }
        />
      )}

      {/* Populated Table */}
      {!isLoading && !error && filteredActions.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50/75 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Action & Details</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Owner / Deadline</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Operations</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredActions.map((act) => {
                  const isWorking = processingId === act.id;
                  return (
                    <tr key={act.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-4 max-w-sm">
                        <span className="font-semibold text-slate-900 block leading-snug">
                          {act.description}
                        </span>
                        <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400 font-mono">
                          <Link
                            to={`/meetings/${act.meeting_id}`}
                            className="hover:text-blue-600 hover:underline"
                          >
                            Meeting: {act.meeting_id.substring(0, 8)}...
                          </Link>
                          {act.needs_clarification && (
                            <span className="text-amber-800 bg-amber-100 border border-amber-300 font-sans px-1.5 py-0.2 rounded font-semibold">
                              Needs Clarification
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <StatusBadge status={act.type} type="type" />
                      </td>

                      <td className="py-3 px-4 font-mono text-[11px]">
                        <span className="text-slate-800 block font-medium">
                          {act.owner || <span className="text-amber-700 italic font-normal">Unassigned</span>}
                        </span>
                        {act.deadline_text && (
                          <span className="text-slate-400 block text-[10px]">{act.deadline_text}</span>
                        )}
                        {act.recipient_email && (
                          <span className="text-slate-500 block text-[10px]">{act.recipient_email}</span>
                        )}
                      </td>

                      <td className="py-3 px-4">
                        <StatusBadge status={act.approval_status} />
                      </td>

                      <td className="py-3 px-4 text-right space-x-1 shrink-0">
                        {/* Edit */}
                        {act.approval_status !== 'succeeded' && act.approval_status !== 'executing' && (
                          <button
                            onClick={() => setSelectedActionForEdit(act)}
                            className="p-1 text-slate-500 hover:text-slate-900 rounded hover:bg-slate-100 transition-colors"
                            title="Edit action"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {/* Approve */}
                        {(act.approval_status === 'pending' || act.approval_status === 'edited' || act.approval_status === 'rejected' || act.approval_status === 'failed') && (
                          <button
                            onClick={() => handleApprove(act.id)}
                            disabled={isWorking || act.needs_clarification}
                            className="p-1 text-emerald-600 hover:text-emerald-800 rounded hover:bg-emerald-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            title={act.needs_clarification ? 'Resolve clarification before approving' : 'Approve'}
                          >
                            {isWorking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                          </button>
                        )}

                        {/* Reject */}
                        {(act.approval_status === 'pending' || act.approval_status === 'edited' || act.approval_status === 'approved') && (
                          <button
                            onClick={() => handleReject(act.id)}
                            disabled={isWorking}
                            className="p-1 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 transition-colors"
                            title="Reject"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {/* Execute */}
                        {act.approval_status === 'approved' && (
                          <button
                            onClick={() => handleExecute(act.id)}
                            disabled={isWorking}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded transition-colors shadow-2xs"
                            title="Execute action"
                          >
                            {isWorking ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3 fill-current" />}
                            <span>Execute</span>
                          </button>
                        )}

                        {/* View Result */}
                        {act.approval_status === 'succeeded' && act.execution_result && (
                          <button
                            onClick={() => setSelectedResult(act.execution_result)}
                            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition-colors"
                          >
                            <Eye className="w-3 h-3" />
                            <span>Result</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Edit Action Modal */}
      {selectedActionForEdit && (
        <EditActionModal
          isOpen={true}
          action={selectedActionForEdit}
          onClose={() => setSelectedActionForEdit(null)}
          onActionUpdated={(updated) => {
            setActions((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
            setSelectedActionForEdit(null);
          }}
        />
      )}

      {/* Execution Result Modal */}
      {selectedResult && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedResult(null)}
          title="Mock Execution Result"
          subtitle="Simulated action dispatched in local mock environment"
        >
          <div className="space-y-4 text-xs">
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded text-emerald-900 font-medium">
              {selectedResult.message}
            </div>

            <div className="space-y-2">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                Execution Payload
              </span>
              <pre className="p-3 bg-slate-900 text-slate-100 rounded text-[11px] font-mono overflow-x-auto leading-relaxed">
                {JSON.stringify(selectedResult, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setSelectedResult(null)}
                className="px-3.5 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors shadow-2xs"
              >
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
