import React, { useState } from 'react';
import StatusBadge from '../common/StatusBadge';
import Modal from '../common/Modal';
import EditActionModal from '../actions/EditActionModal';
import { api } from '../../services/api';
import { CheckCircle2, HelpCircle, Check, X, Play, Edit3, Eye, AlertCircle, Loader2, RefreshCw } from 'lucide-react';

export default function ActionsTab({ meeting, onActionChanged }) {
  const [selectedActionForEdit, setSelectedActionForEdit] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);
  const [processingId, setProcessingId] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  const actions = meeting.actions || [];
  const decisions = meeting.decisions || [];
  const openQuestions = meeting.open_questions || [];

  async function handleApprove(actionId) {
    setProcessingId(actionId);
    setErrorMsg('');
    try {
      const updated = await api.approveAction(actionId);
      onActionChanged(updated);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to approve action.');
    } finally {
      setProcessingId(null);
    }
  }

  async function handleReject(actionId) {
    setProcessingId(actionId);
    setErrorMsg('');
    try {
      const updated = await api.rejectAction(actionId);
      onActionChanged(updated);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to reject action.');
    } finally {
      setProcessingId(null);
    }
  }

  async function handleExecute(actionId) {
    setProcessingId(actionId);
    setErrorMsg('');
    try {
      const updated = await api.executeAction(actionId);
      onActionChanged(updated);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to execute action.');
    } finally {
      setProcessingId(null);
    }
  }

  if (meeting.status !== 'analyzed') {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-8 text-center text-slate-500">
        <p className="text-sm">Workflow has not been extracted for this meeting yet.</p>
        <p className="text-xs text-slate-400 mt-1">
          Transcribe the audio and run workflow analysis from the Overview tab first.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-md text-xs text-rose-700 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <div className="flex-1">{errorMsg}</div>
        </div>
      )}

      {/* Decisions Section */}
      {decisions.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="w-4 h-4 text-teal-600" />
            <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
              Recorded Decisions ({decisions.length})
            </h3>
          </div>
          <div className="space-y-2">
            {decisions.map((dec, idx) => (
              <div key={idx} className="p-3 bg-slate-50/70 border border-slate-100 rounded text-xs space-y-1">
                <span className="font-semibold text-slate-900 block">{dec.description}</span>
                {dec.evidence && (
                  <span className="text-[11px] text-slate-500 font-mono italic block">
                    Evidence: "{dec.evidence}"
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Open Questions Section */}
      {openQuestions.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
          <div className="flex items-center gap-2 mb-3">
            <HelpCircle className="w-4 h-4 text-amber-600" />
            <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
              Open Questions ({openQuestions.length})
            </h3>
          </div>
          <div className="space-y-2">
            {openQuestions.map((q, idx) => (
              <div key={idx} className="p-3 bg-amber-50/30 border border-amber-100/70 rounded text-xs space-y-1">
                <span className="font-semibold text-slate-900 block">{q.question}</span>
                {q.evidence && (
                  <span className="text-[11px] text-slate-500 font-mono italic block">
                    Evidence: "{q.evidence}"
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Proposed Action Items Section */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
            Proposed Action Items ({actions.length})
          </h3>
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

        {actions.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No action items were identified in this meeting.</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {actions.map((act) => {
              const isWorking = processingId === act.id;
              return (
                <div key={act.id} className="py-4 first:pt-0 last:pb-0 space-y-2.5">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                    <div className="space-y-1 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={act.type} type="type" />
                        <StatusBadge status={act.approval_status} />
                        {act.needs_clarification && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-200">
                            Needs Clarification
                          </span>
                        )}
                      </div>
                      <h4 className="text-sm font-semibold text-slate-900">{act.description}</h4>
                    </div>

                    {/* Operational Action Buttons */}
                    <div className="flex flex-wrap items-center gap-1.5 shrink-0 pt-1 sm:pt-0">
                      {/* Edit Button */}
                      {act.approval_status !== 'succeeded' && act.approval_status !== 'executing' && (
                        <button
                          onClick={() => setSelectedActionForEdit(act)}
                          disabled={isWorking}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors shadow-2xs"
                          title="Edit action details"
                        >
                          <Edit3 className="w-3 h-3 text-slate-500" />
                          <span>Edit</span>
                        </button>
                      )}

                      {/* Approve Button */}
                      {(act.approval_status === 'pending' || act.approval_status === 'edited' || act.approval_status === 'rejected' || act.approval_status === 'failed') && (
                        <button
                          onClick={() => handleApprove(act.id)}
                          disabled={isWorking || act.needs_clarification}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded hover:bg-emerald-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-2xs"
                          title={act.needs_clarification ? 'Resolve clarification via Edit before approving' : 'Approve for execution'}
                        >
                          {isWorking ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Check className="w-3 h-3" />
                          )}
                          <span>Approve</span>
                        </button>
                      )}

                      {/* Reject Button */}
                      {(act.approval_status === 'pending' || act.approval_status === 'edited' || act.approval_status === 'approved') && (
                        <button
                          onClick={() => handleReject(act.id)}
                          disabled={isWorking}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-600 bg-white border border-slate-200 rounded hover:bg-slate-50 hover:text-rose-600 transition-colors shadow-2xs"
                          title="Reject action"
                        >
                          <X className="w-3 h-3" />
                          <span>Reject</span>
                        </button>
                      )}

                      {/* Execute Button */}
                      {act.approval_status === 'approved' && (
                        <button
                          onClick={() => handleExecute(act.id)}
                          disabled={isWorking}
                          className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors rounded shadow-xs"
                          title="Execute mock action"
                        >
                          {isWorking ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Play className="w-3 h-3 fill-current" />
                          )}
                          <span>Execute</span>
                        </button>
                      )}

                      {/* View Execution Result Button */}
                      {act.approval_status === 'succeeded' && act.execution_result && (
                        <button
                          onClick={() => setSelectedResult(act.execution_result)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors shadow-2xs"
                        >
                          <Eye className="w-3 h-3 text-blue-600" />
                          <span>View Result</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Metadata fields (owner, deadline, email) */}
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600 font-mono bg-slate-50/50 p-2 rounded border border-slate-100">
                    <div>
                      <span className="text-slate-400 font-sans">Owner: </span>
                      <span className={act.owner ? 'font-semibold text-slate-800' : 'italic text-amber-700'}>
                        {act.owner || 'Unassigned'}
                      </span>
                    </div>

                    {act.deadline_text && (
                      <div>
                        <span className="text-slate-400 font-sans">Deadline: </span>
                        <span className="text-slate-800">{act.deadline_text}</span>
                      </div>
                    )}

                    {act.recipient_email && (
                      <div>
                        <span className="text-slate-400 font-sans">To: </span>
                        <span className="text-slate-800">{act.recipient_email}</span>
                      </div>
                    )}

                    {act.confidence && (
                      <div>
                        <span className="text-slate-400 font-sans">Confidence: </span>
                        <span className="text-slate-700 capitalize">{act.confidence}</span>
                      </div>
                    )}
                  </div>

                  {/* Transcript quote evidence */}
                  {act.evidence && (
                    <div className="text-[11px] text-slate-500 font-mono italic pl-2 border-l-2 border-slate-200">
                      "{act.evidence}"
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Edit Action Modal */}
      {selectedActionForEdit && (
        <EditActionModal
          isOpen={true}
          action={selectedActionForEdit}
          onClose={() => setSelectedActionForEdit(null)}
          onActionUpdated={(updated) => {
            onActionChanged(updated);
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
