import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import toast from 'react-hot-toast';
import { api } from '../services/api';
import { Send, Check, X, RefreshCw, Loader2 } from 'lucide-react';
import clsx from 'clsx';

export const EmailGenerator = ({ onActionComplete }) => {
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    checkDraft();
  }, []);

  const checkDraft = async () => {
    try {
      const res = await api.getDraft();
      if (res.data.exists) {
        setDraft(res.data.content);
      } else {
        setDraft(null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    
    const toastId = toast.loading('Generating email report...');
    
    try {
      const res = await api.generateEmail();
      setDraft(res.data.content);
      if (onActionComplete) onActionComplete();
      
      toast.success('Email report generated successfully!', { id: toastId });
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to generate email. Check backend logs.';
      setError(errorMsg);
      toast.error(errorMsg, { id: toastId });
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    setLoading(true);
    
    const toastId = toast.loading('Approving draft...');
    
    try {
      await api.approveDraft();
      setDraft(null);
      if (onActionComplete) onActionComplete();
      
      toast.success('Draft approved and archived successfully! 🎉', { 
        id: toastId,
        duration: 5000 
      });
    } catch (err) {
      const errorMsg = err.response?.data?.message || 'Failed to approve draft.';
      setError(errorMsg);
      toast.error(errorMsg, { id: toastId });
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    // Use toast for confirmation instead of browser confirm
    const confirmReject = window.confirm('Are you sure you want to discard this draft?');
    if (!confirmReject) return;
    
    setLoading(true);
    const toastId = toast.loading('Discarding draft...');
    
    try {
      await api.rejectDraft();
      setDraft(null);
      toast.success('Draft discarded', { id: toastId });
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to reject draft.';
      setError(errorMsg);
      toast.error(errorMsg, { id: toastId });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Daily Report Generation</h2>
        {!draft && (
          <button
            onClick={handleGenerate}
            disabled={loading}
            className={clsx(
              "flex items-center px-4 py-2 rounded-lg text-white font-medium transition-colors",
              loading ? "bg-blue-300 cursor-not-allowed" : "bg-blue-500 hover:bg-blue-600"
            )}
            aria-label="Generate new daily report email"
          >
            {loading ? (
              <Loader2 className="animate-spin mr-2" size={18} aria-hidden="true" />
            ) : (
              <RefreshCw className="mr-2" size={18} aria-hidden="true" />
            )}
            Generate New Report
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6 text-sm">
          {error}
        </div>
      )}

      {draft && (
        <div className="space-y-6">
          <div className="bg-gray-50 p-6 rounded-lg border border-gray-200 prose prose-sm max-w-none max-h-[600px] overflow-y-auto">
            <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{draft}</ReactMarkdown>
          </div>

          <div className="flex justify-end space-x-4">
            <button
              onClick={handleReject}
              disabled={loading}
              className="flex items-center px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium"
              aria-label="Discard current draft"
            >
              <X className="mr-2" size={18} aria-hidden="true" />
              Discard
            </button>
            <button
              onClick={handleApprove}
              disabled={loading}
              className="flex items-center px-6 py-2 rounded-lg bg-green-500 hover:bg-green-600 text-white font-medium"
              aria-label="Approve draft and archive it"
            >
              {loading ? (
                <Loader2 className="animate-spin mr-2" size={18} aria-hidden="true" />
              ) : (
                <Check className="mr-2" size={18} aria-hidden="true" />
              )}
              Approve & Archive
            </button>
          </div>
        </div>
      )}
      
      {!draft && !loading && (
        <div className="text-center py-12 text-gray-400 bg-gray-50 rounded-lg border border-dashed border-gray-200">
          <Send size={48} className="mx-auto mb-4 opacity-20" />
          <p>No draft currently active. Generate a new report to get started.</p>
        </div>
      )}
    </div>
  );
};

