import React, { useMemo, memo } from 'react';
import { Card, Title } from './ui/Card';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { it } from 'date-fns/locale';
import { RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';

// Colori
const LINE_COLOR = '#3b82f6';  // blue-500
const AVERAGE_COLOR = '#ef4444';  // red-500

/**
 * Custom tooltip component - memoized
 */
const CustomTooltipContent = memo(({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;

  const dataPoint = payload[0]?.payload;
  if (!dataPoint) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 min-w-[140px]">
      <p className="text-sm font-medium text-gray-900 mb-1">
        {dataPoint.fullDate}
      </p>
      <p className="text-lg font-bold text-blue-600">
        {dataPoint.value?.toFixed(2)}%
      </p>
    </div>
  );
});

CustomTooltipContent.displayName = 'CustomTooltipContent';

/**
 * Widget Stats component - mostra ultimo valore e variazione
 */
const StatsWidget = memo(({ lastValue, variation, loading }) => {
  if (loading) {
    return (
      <div className="flex items-center gap-2 animate-pulse">
        <div className="h-6 w-16 bg-gray-200 rounded"></div>
        <div className="h-5 w-12 bg-gray-200 rounded"></div>
      </div>
    );
  }

  const isPositive = variation >= 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;

  return (
    <div className="flex items-center gap-3">
      <span className="text-xl font-bold text-gray-900">
        {lastValue?.toFixed(2)}%
      </span>
      <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-sm font-medium ${
        isPositive 
          ? 'bg-green-50 text-green-700' 
          : 'bg-red-50 text-red-700'
      }`}>
        <Icon size={14} />
        <span>{isPositive ? '+' : ''}{variation?.toFixed(1)}%</span>
      </div>
    </div>
  );
});

StatsWidget.displayName = 'StatsWidget';

/**
 * CRChart component - Grafico Conversion Rate con media e variazione
 */
function CRChartComponent({
  title,
  dataKey, // 'cr_commodity' | 'cr_lucegas'
  data = [],
  average = 0,
  loading = false
}) {
  // Trasforma i dati per il grafico
  const chartData = useMemo(() => {
    return data.map(item => ({
      date: format(parseISO(item.date), 'dd/MM', { locale: it }),
      fullDate: item.date,
      value: item[dataKey]
    }));
  }, [data, dataKey]);

  // Calcola ultimo valore e variazione dalla media
  const { lastValue, variation } = useMemo(() => {
    if (!data.length || !average) {
      return { lastValue: 0, variation: 0 };
    }
    
    const last = data[data.length - 1]?.[dataKey] || 0;
    const var_ = average > 0 ? ((last - average) / average) * 100 : 0;
    
    return { lastValue: last, variation: var_ };
  }, [data, dataKey, average]);

  return (
    <Card className="h-full">
      <div className="flex items-center justify-between mb-4">
        {/* Titolo a sinistra */}
        <Title>{title}</Title>
        
        {/* Widget stats a destra */}
        <StatsWidget 
          lastValue={lastValue} 
          variation={variation} 
          loading={loading} 
        />
      </div>

      {loading ? (
        <div className="h-56 flex items-center justify-center">
          <RefreshCw size={24} className="text-gray-400 animate-spin" />
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#6b7280' }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#6b7280' }}
              tickLine={false}
              axisLine={false}
              width={45}
              tickFormatter={(value) => `${value.toFixed(1)}%`}
              domain={['auto', 'auto']}
            />
            <Tooltip content={<CustomTooltipContent />} />
            
            {/* Linea di riferimento per la media */}
            {average > 0 && (
              <ReferenceLine
                y={average}
                stroke={AVERAGE_COLOR}
                strokeDasharray="5 5"
                strokeWidth={2}
                label={{
                  value: `Media: ${average.toFixed(2)}%`,
                  position: 'right',
                  fill: AVERAGE_COLOR,
                  fontSize: 10,
                  fontWeight: 500
                }}
              />
            )}
            
            {/* Linea principale */}
            <Line
              type="monotone"
              dataKey="value"
              stroke={LINE_COLOR}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: LINE_COLOR }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

// Export memoized component
export const CRChart = memo(CRChartComponent);

CRChart.displayName = 'CRChart';

