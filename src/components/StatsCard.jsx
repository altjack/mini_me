import React, { memo } from 'react';
import { Calendar, FileText, TrendingUp } from 'lucide-react';

/**
 * Individual stat item - memoized to prevent unnecessary re-renders
 */
const StatItem = memo(({ icon: Icon, label, value, subtext }) => (
  <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex items-start space-x-4">
    <div className="p-3 bg-blue-50 rounded-lg text-blue-600">
      <Icon size={24} />
    </div>
    <div>
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <h3 className="text-2xl font-bold text-gray-900 mt-1">{value}</h3>
      {subtext && <p className="text-xs text-gray-400 mt-1">{subtext}</p>}
    </div>
  </div>
));

StatItem.displayName = 'StatItem';

/**
 * Stats card component - memoized with custom comparison
 */
const StatsCardComponent = ({ stats, loading }) => {
  if (loading) {
    return <div className="animate-pulse h-32 bg-gray-200 rounded-xl w-full"></div>;
  }

  if (!stats) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <StatItem 
        icon={FileText} 
        label="Total Records" 
        value={stats.record_count} 
        subtext="Daily reports stored"
      />
      <StatItem 
        icon={Calendar} 
        label="Latest Date" 
        value={stats.latest_available_date || 'N/A'} 
        subtext={`Range: ${stats.min_date} - ${stats.max_date}`}
      />
      <StatItem 
        icon={TrendingUp} 
        label="Avg Conversion" 
        value={Math.round(stats.avg_conversioni || 0)} 
        subtext="SWI Conversions"
      />
    </div>
  );
};

// Memoize with shallow comparison - re-renders only when stats or loading change
export const StatsCard = memo(StatsCardComponent, (prevProps, nextProps) => {
  return (
    prevProps.loading === nextProps.loading &&
    JSON.stringify(prevProps.stats) === JSON.stringify(nextProps.stats)
  );
});

StatsCard.displayName = 'StatsCard';
