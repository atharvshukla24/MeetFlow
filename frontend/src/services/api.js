/**
 * MeetFlow API Service Client
 * Connects directly to FastAPI backend without hardcoded demo data.
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/+$/, '');

/**
 * Handle API responses and extract meaningful error details.
 */
async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      if (errorJson && errorJson.detail) {
        if (typeof errorJson.detail === 'string') {
          errorDetail = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          errorDetail = errorJson.detail.map(d => d.msg || JSON.stringify(d)).join('; ');
        } else {
          errorDetail = JSON.stringify(errorJson.detail);
        }
      }
    } catch {
      // Fallback if not JSON
    }
    const error = new Error(errorDetail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export const api = {
  getBaseUrl() {
    return API_BASE_URL;
  },

  /** Check API health */
  async checkHealth() {
    const res = await fetch(`${API_BASE_URL}/health`);
    return handleResponse(res);
  },

  // ==========================================
  // MEETINGS
  // ==========================================

  /** List all meetings ordered by creation date descending */
  async listMeetings() {
    const res = await fetch(`${API_BASE_URL}/meetings`);
    return handleResponse(res);
  },

  /** Get meeting details by ID */
  async getMeeting(meetingId) {
    const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}`);
    return handleResponse(res);
  },

  /**
   * Upload audio file for meeting
   * @param {File} file
   * @param {string} title
   */
  async uploadMeeting(file, title = '') {
    const formData = new FormData();
    formData.append('file', file);
    if (title && title.trim()) {
      formData.append('title', title.trim());
    }

    const res = await fetch(`${API_BASE_URL}/meetings/upload`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },

  /** Run speech-to-text transcription */
  async transcribeMeeting(meetingId) {
    const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}/transcribe`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  /** Retrieve transcript text and metadata */
  async getTranscript(meetingId) {
    const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}/transcript`);
    return handleResponse(res);
  },

  /** Edit transcript text */
  async updateTranscript(meetingId, transcriptText) {
    const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}/transcript`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript: transcriptText }),
    });
    return handleResponse(res);
  },

  /** Run workflow extraction on transcript */
  async analyzeMeeting(meetingId) {
    const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}/analyze`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  /** Get extracted workflow (actions, decisions, open questions, summary) */
  async getWorkflow(meetingId) {
    const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}/workflow`);
    return handleResponse(res);
  },

  // ==========================================
  // ACTIONS
  // ==========================================

  /** List all extracted actions across meetings */
  async listActions() {
    const res = await fetch(`${API_BASE_URL}/actions`);
    return handleResponse(res);
  },

  /** Get an individual action by ID */
  async getAction(actionId) {
    const res = await fetch(`${API_BASE_URL}/actions/${actionId}`);
    return handleResponse(res);
  },

  /** Edit an action item */
  async updateAction(actionId, actionData) {
    const res = await fetch(`${API_BASE_URL}/actions/${actionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(actionData),
    });
    return handleResponse(res);
  },

  /** Approve an action */
  async approveAction(actionId) {
    const res = await fetch(`${API_BASE_URL}/actions/${actionId}/approve`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  /** Reject an action */
  async rejectAction(actionId) {
    const res = await fetch(`${API_BASE_URL}/actions/${actionId}/reject`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  /** Execute an action */
  async executeAction(actionId) {
    const res = await fetch(`${API_BASE_URL}/actions/${actionId}/execute`, {
      method: 'POST',
    });
    return handleResponse(res);
  },
};
