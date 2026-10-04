import React, { useState, useRef } from 'react';
import Modal from '../common/Modal';
import { api } from '../../services/api';
import { UploadCloud, FileAudio, AlertCircle, Loader2 } from 'lucide-react';

const ALLOWED_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.aac', '.ogg', '.flac'];
const MAX_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

export default function UploadModal({ isOpen, onClose, onSuccess }) {
  const [title, setTitle] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);

  function resetForm() {
    setTitle('');
    setSelectedFile(null);
    setError('');
    setIsUploading(false);
  }

  function handleClose() {
    if (isUploading) return;
    resetForm();
    onClose();
  }

  function validateAndSetFile(file) {
    setError('');
    if (!file) return;

    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file type (${ext}). Allowed formats: ${ALLOWED_EXTENSIONS.join(', ')}`);
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_SIZE_BYTES) {
      setError(`File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum limit is 50 MB.`);
      setSelectedFile(null);
      return;
    }

    if (file.size === 0) {
      setError('Selected audio file is empty (0 bytes).');
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    if (!title) {
      // Pre-fill title from filename without extension
      const baseName = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
      setTitle(baseName.replace(/[_-]/g, ' '));
    }
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    validateAndSetFile(file);
  }

  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    const file = e.dataTransfer.files?.[0];
    validateAndSetFile(file);
  }

  function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select an audio file to upload.');
      return;
    }

    setIsUploading(true);
    setError('');

    try {
      const createdMeeting = await api.uploadMeeting(selectedFile, title);
      resetForm();
      onSuccess(createdMeeting);
    } catch (err) {
      setError(err.message || 'Failed to upload audio recording.');
      setIsUploading(false);
    }
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Upload Meeting Recording"
      subtitle="Select a pre-recorded meeting audio file for processing"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 rounded-md bg-rose-50 border border-rose-200 flex items-start gap-2 text-xs text-rose-700">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="flex-1">{error}</div>
          </div>
        )}

        {/* Title Input */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">
            Meeting Title <span className="text-slate-400 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={isUploading}
            placeholder="e.g. Sprint Planning Sync"
            className="w-full px-3 py-2 text-xs rounded border border-slate-300 focus:outline-hidden focus:border-blue-600 focus:ring-1 focus:ring-blue-600 bg-white disabled:bg-slate-50 disabled:text-slate-400"
          />
        </div>

        {/* Drag & Drop File Area */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">
            Audio Recording File <span className="text-rose-500">*</span>
          </label>
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => !isUploading && fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              selectedFile
                ? 'border-blue-300 bg-blue-50/30'
                : 'border-slate-300 hover:border-slate-400 hover:bg-slate-50/50'
            } ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".wav,.mp3,.m4a,.aac,.ogg,.flac"
              onChange={handleFileChange}
              disabled={isUploading}
              className="hidden"
            />

            {selectedFile ? (
              <div className="flex flex-col items-center">
                <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center mb-2">
                  <FileAudio className="w-5 h-5" />
                </div>
                <span className="text-xs font-semibold text-slate-800 break-all">{selectedFile.name}</span>
                <span className="text-[11px] text-slate-500 mt-0.5">{formatBytes(selectedFile.size)}</span>
                <span className="text-[10px] text-blue-600 underline mt-2">Click to replace file</span>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center mb-2">
                  <UploadCloud className="w-5 h-5" />
                </div>
                <span className="text-xs font-medium text-slate-700">
                  Click to select audio or drag and drop
                </span>
                <span className="text-[11px] text-slate-400 mt-1">
                  WAV, MP3, M4A, AAC, OGG, FLAC (max 50 MB)
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Buttons */}
        <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
          <button
            type="button"
            onClick={handleClose}
            disabled={isUploading}
            className="px-3.5 py-1.5 rounded text-xs font-medium text-slate-700 hover:bg-slate-100 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!selectedFile || isUploading}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-xs"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Uploading...</span>
              </>
            ) : (
              <span>Upload Recording</span>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
