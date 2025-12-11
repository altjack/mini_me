import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { api } from '../services/api';
import { Database, Calendar, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { format, subDays } from 'date-fns';

export const BackfillPanel = ({ onActionComplete }) => {
  const [startDate, setStartDate] = useState(format(subDays(new Date(), 7), 'yyyy-MM-dd'));
  const [endDate, setEndDate] = useState(format(subDays(new Date(), 1), 'yyyy-MM-dd'));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleBackfill = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    
    const toastId = toast.loading('Backfilling data...');
    
    try {
      const res = await api.backfill(startDate, endDate);
      setResult({
        success: true,
        data: res.data
      });
      
      if (onActionComplete) onActionComplete();
      
      const successCount = res.data.data?.successful || 0;
      toast.success(`Backfill completed! ${successCount} dates processed successfully.`, { 
        id: toastId,
        duration: 5000 
      });
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Backfill failed';
      setResult({
        success: false,
        error: errorMsg
      });
      toast.error(errorMsg, { id: toastId });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center mb-6">
        <Database className="text-blue-500 mr-3" size={24} />
        <h2 className="text-xl font-semibold text-gray-800">Data Backfill</h2>
      </div>

      <form onSubmit={handleBackfill} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-3 text-gray-400" size={16} />
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                required
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-3 text-gray-400" size={16} />
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                required
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gray-900 hover:bg-gray-800 text-white font-medium py-2.5 rounded-lg transition-colors flex justify-center items-center"
        >
          {loading ? (
            <>
              <Loader2 className="animate-spin mr-2" size={18} />
              Processing Backfill...
            </>
          ) : (
            'Start Backfill Process'
          )}
        </button>
      </form>

      {result && (
        <div className={`mt-6 p-4 rounded-lg ${result.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          <div className="flex items-start">
            {result.success ? <CheckCircle className="mr-2 mt-0.5" size={18} /> : <AlertCircle className="mr-2 mt-0.5" size={18} />}
            <div>
              <p className="font-medium">{result.success ? 'Backfill Completed' : 'Error'}</p>
              {result.success && (
                <p className="text-sm mt-1">
                  Successfully processed {result.data.completed} of {result.data.total} days.
                </p>
              )}
              {!result.success && <p className="text-sm mt-1">{result.error}</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

