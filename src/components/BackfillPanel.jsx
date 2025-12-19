import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { useBackfill } from '../context/BackfillContext';
import { Database, Calendar, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { format, subDays } from 'date-fns';

export const BackfillPanel = ({ onActionComplete }) => {
  // Local state for form inputs
  const [startDate, setStartDate] = useState(format(subDays(new Date(), 7), 'yyyy-MM-dd'));
  const [endDate, setEndDate] = useState(format(subDays(new Date(), 1), 'yyyy-MM-dd'));

  // Global backfill state from context
  const { isRunning, result, error, params, startBackfill, clearResult } = useBackfill();

  // Show toast when backfill completes (even if user navigated away and came back)
  useEffect(() => {
    // Only show toast if there's a new result that we haven't shown yet
    if (result && !isRunning) {
      if (result.success) {
        const successCount = result.data?.data?.successful || result.data?.completed || 0;
        toast.success(`Backfill completed! ${successCount} dates processed successfully.`, {
          duration: 5000,
        });
      } else if (result.error) {
        toast.error(result.error);
      }
    }
  }, [result, isRunning]);

  // Validate date format and range
  const isValidDate = (dateString) => {
    const regex = /^\d{4}-\d{2}-\d{2}$/;
    if (!regex.test(dateString)) return false;
    const date = new Date(dateString);
    return !isNaN(date.getTime());
  };

  const handleBackfill = async (e) => {
    e.preventDefault();

    // Client-side validation
    if (!isValidDate(startDate) || !isValidDate(endDate)) {
      toast.error('Invalid date format. Please use YYYY-MM-DD format.');
      return;
    }

    const start = new Date(startDate);
    const end = new Date(endDate);

    if (start > end) {
      toast.error('Start date must be before or equal to end date.');
      return;
    }

    // Prevent excessive date ranges (e.g., max 365 days)
    const daysDiff = Math.floor((end - start) / (1000 * 60 * 60 * 24));
    if (daysDiff > 365) {
      toast.error('Date range cannot exceed 365 days.');
      return;
    }

    // Clear previous result before starting
    clearResult();

    const toastId = toast.loading('Backfilling data...');

    const { success, data, error: backfillError } = await startBackfill(
      startDate,
      endDate,
      onActionComplete
    );

    if (success) {
      const successCount = data?.data?.successful || data?.completed || 0;
      toast.success(`Backfill completed! ${successCount} dates processed successfully.`, {
        id: toastId,
        duration: 5000,
      });
    } else {
      toast.error(backfillError || 'Backfill failed', { id: toastId });
    }
  };

  // Determine what result to show (could be from current session or from context)
  const displayResult = result;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center mb-6">
        <Database className="text-blue-500 mr-3" size={24} />
        <h2 className="text-xl font-semibold text-gray-800">Data Backfill</h2>
      </div>

      {/* Show running indicator if backfill is in progress */}
      {isRunning && params && (
        <div className="mb-4 p-3 bg-blue-50 text-blue-700 rounded-lg flex items-center">
          <Loader2 className="animate-spin mr-2" size={18} />
          <div>
            <p className="font-medium">Backfill in progress...</p>
            <p className="text-sm">
              Processing dates from {params.startDate} to {params.endDate}
            </p>
          </div>
        </div>
      )}

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
                disabled={isRunning}
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all disabled:bg-gray-50 disabled:text-gray-400"
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
                disabled={isRunning}
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all disabled:bg-gray-50 disabled:text-gray-400"
                required
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={isRunning}
          className="w-full bg-gray-900 hover:bg-gray-800 text-white font-medium py-2.5 rounded-lg transition-colors flex justify-center items-center disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRunning ? (
            <>
              <Loader2 className="animate-spin mr-2" size={18} />
              Processing Backfill...
            </>
          ) : (
            'Start Backfill Process'
          )}
        </button>
      </form>

      {displayResult && !isRunning && (
        <div
          className={`mt-6 p-4 rounded-lg ${
            displayResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}
        >
          <div className="flex items-start">
            {displayResult.success ? (
              <CheckCircle className="mr-2 mt-0.5" size={18} />
            ) : (
              <AlertCircle className="mr-2 mt-0.5" size={18} />
            )}
            <div className="flex-1">
              <p className="font-medium">
                {displayResult.success ? 'Backfill Completed' : 'Error'}
              </p>
              {displayResult.success && displayResult.data && (
                <p className="text-sm mt-1">
                  Successfully processed{' '}
                  {displayResult.data.completed || displayResult.data.data?.successful || 0} of{' '}
                  {displayResult.data.total || displayResult.data.data?.total || 0} days.
                </p>
              )}
              {!displayResult.success && (
                <p className="text-sm mt-1">{displayResult.error || error}</p>
              )}
              {displayResult.completedAt && (
                <p className="text-xs mt-2 opacity-70">
                  Completed at {new Date(displayResult.completedAt).toLocaleTimeString()}
                </p>
              )}
            </div>
            <button
              onClick={clearResult}
              className="text-sm underline hover:no-underline ml-2"
              aria-label="Dismiss result"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
