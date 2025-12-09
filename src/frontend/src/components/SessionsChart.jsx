import React, { useState, useMemo } from 'react';
import { Card, Title, Text } from '@tremor/react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { it } from 'date-fns/locale';
import { RefreshCw } from 'lucide-react';

// Colori per i canali
const CHANNEL_COLORS = {
  'Direct': '#3b82f6',           // blue-500
  'Organic Search': '#10b981',   // emerald-500
  'Paid Search': '#f59e0b',      // amber-500
  'Paid Media e Display': '#8b5cf6', // violet-500
};

const TOTAL_COLOR = '#3b82f6'; // blue-500

export function SessionsChart({ 
  title, 
  dataKey, // 'commodity' | 'lucegas'
  totals = [], 
  byChannel = [],
  loading = false,
  channels = []
}) {
  const [activeTab, setActiveTab] = useState('totale');
  const [hiddenChannels, setHiddenChannels] = useState(new Set());

  // Trasforma i dati per il grafico "Totale"
  const totalChartData = useMemo(() => {
    return totals.map(item => ({
      date: format(parseISO(item.date), 'dd/MM', { locale: it }),
      fullDate: item.date,
      value: item[dataKey]
    }));
  }, [totals, dataKey]);

  // Trasforma i dati per il grafico "Per Canale"
  const channelChartData = useMemo(() => {
    // Raggruppa per data
    const grouped = {};
    
    byChannel.forEach(item => {
      const dateKey = item.date;
      if (!grouped[dateKey]) {
        grouped[dateKey] = {
          date: format(parseISO(item.date), 'dd/MM', { locale: it }),
          fullDate: item.date
        };
      }
      grouped[dateKey][item.channel] = item[dataKey];
    });
    
    return Object.values(grouped).sort((a, b) => 
      a.fullDate.localeCompare(b.fullDate)
    );
  }, [byChannel, dataKey]);

  // Toggle visibilità canale
  const toggleChannel = (channel) => {
    setHiddenChannels(prev => {
      const next = new Set(prev);
      if (next.has(channel)) {
        next.delete(channel);
      } else {
        next.add(channel);
      }
      return next;
    });
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null;
    
    const dataPoint = payload[0]?.payload;
    if (!dataPoint) return null;

    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 min-w-[180px]">
        <p className="text-sm font-medium text-gray-900 mb-2">
          {dataPoint.fullDate}
        </p>
        {activeTab === 'totale' ? (
          <p className="text-lg font-bold text-blue-600">
            {dataPoint.value?.toLocaleString('it-IT')} sessioni
          </p>
        ) : (
          <div className="space-y-1">
            {payload.map((entry, index) => (
              <div key={index} className="flex justify-between items-center gap-4">
                <div className="flex items-center gap-2">
                  <span 
                    className="w-2 h-2 rounded-full" 
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-xs text-gray-600">{entry.dataKey}</span>
                </div>
                <span className="text-sm font-medium">
                  {entry.value?.toLocaleString('it-IT')}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Custom legend con click handler
  const renderLegend = () => {
    return (
      <div className="flex flex-wrap justify-center gap-3 mt-2">
        {channels.map(channel => (
          <button
            key={channel}
            onClick={() => toggleChannel(channel)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-opacity ${
              hiddenChannels.has(channel) ? 'opacity-40' : 'opacity-100'
            }`}
          >
            <span 
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: CHANNEL_COLORS[channel] || '#6b7280' }}
            />
            <span className="text-gray-700">{channel}</span>
          </button>
        ))}
      </div>
    );
  };

  return (
    <Card className="h-full">
      <div className="flex items-center justify-between mb-4">
        <Title>{title}</Title>
        
        {/* Tabs */}
        <div className="flex bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setActiveTab('totale')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              activeTab === 'totale' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Totale
          </button>
          <button
            onClick={() => setActiveTab('canale')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              activeTab === 'canale' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Per Canale
          </button>
        </div>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center">
          <RefreshCw size={24} className="text-gray-400 animate-spin" />
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={240}>
            {activeTab === 'totale' ? (
              <LineChart data={totalChartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
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
                  width={50}
                  tickFormatter={(value) => value >= 1000 ? `${(value/1000).toFixed(0)}k` : value}
                />
                <Tooltip content={<CustomTooltip />} />
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke={TOTAL_COLOR}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: TOTAL_COLOR }}
                />
              </LineChart>
            ) : (
              <LineChart data={channelChartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
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
                  width={50}
                  tickFormatter={(value) => value >= 1000 ? `${(value/1000).toFixed(0)}k` : value}
                />
                <Tooltip content={<CustomTooltip />} />
                {channels.map(channel => (
                  <Line 
                    key={channel}
                    type="monotone" 
                    dataKey={channel}
                    stroke={CHANNEL_COLORS[channel] || '#6b7280'}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                    hide={hiddenChannels.has(channel)}
                  />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
          
          {/* Legenda cliccabile per la vista canali */}
          {activeTab === 'canale' && renderLegend()}
        </>
      )}
    </Card>
  );
}

