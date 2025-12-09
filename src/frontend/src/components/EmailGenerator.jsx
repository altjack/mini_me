import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
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
    try {
      const res = await api.generateEmail();
      setDraft(res.data.content);
      if (onActionComplete) onActionComplete();
    } catch (err) {
      setError('Failed to generate email. Check backend logs.');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    setLoading(true);
    try {
      await api.approveDraft();
      setDraft(null);
      if (onActionComplete) onActionComplete();
      alert('Draft approved and archived!');
    } catch (err) {
      setError('Failed to approve draft.');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!confirm('Are you sure you want to discard this draft?')) return;
    setLoading(true);
    try {
      await api.rejectDraft();
      setDraft(null);
    } catch (err) {
      setError('Failed to reject draft.');
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
          >
            {loading ? <Loader2 className="animate-spin mr-2" size={18} /> : <RefreshCw className="mr-2" size={18} />}
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
            <ReactMarkdown>{draft}</ReactMarkdown>
          </div>

          <div className="flex justify-end space-x-4">
            <button
              onClick={handleReject}
              disabled={loading}
              className="flex items-center px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium"
            >
              <X className="mr-2" size={18} />
              Discard
            </button>
            <button
              onClick={handleApprove}
              disabled={loading}
              className="flex items-center px-6 py-2 rounded-lg bg-green-500 hover:bg-green-600 text-white font-medium"
            >
              {loading ? <Loader2 className="animate-spin mr-2" size={18} /> : <Check className="mr-2" size={18} />}
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

