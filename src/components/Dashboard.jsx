import React, { useState, useEffect, useMemo } from 'react';
import { Card, Title, Text } from '@tremor/react';
import toast from 'react-hot-toast';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ReferenceLine,
  Cell
} from 'recharts';
import { format, subDays, parseISO } from 'date-fns';
import { it } from 'date-fns/locale';
import { api } from '../services/api';
import { Calendar, RefreshCw, TrendingUp } from 'lucide-react';
import { SessionsChart } from './SessionsChart';

// Colori per il grafico
const COLORS = {
  weekday: '#3b82f6',  // blue-500
  weekend: '#8b5cf6',  // violet-500
  average: '#ef4444',  // red-500
};

export function Dashboard() {
  const [data, setData] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Sessions data
  const [sessionsData, setSessionsData] = useState({ totals: [], by_channel: [] });
  const [sessionsMeta, setSessionsMeta] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  
  // Date range state (default: ultimi 45 giorni)
  const [endDate, setEndDate] = useState(format(subDays(new Date(), 1), 'yyyy-MM-dd'));
  const [startDate, setStartDate] = useState(format(subDays(new Date(), 45), 'yyyy-MM-dd'));

  const fetchData = async () => {
    setLoading(true);
    setLoadingSessions(true);
    setError(null);
    
    try {
      // Fetch metriche SWI
      const metricsRes = await api.getMetricsRange(startDate, endDate);
      if (metricsRes.data.success) {
        setData(metricsRes.data.data);
        setMeta(metricsRes.data.meta);
      } else {
        const errorMsg = metricsRes.data.error || 'Errore nel caricamento dati SWI';
        setError(errorMsg);
        toast.error(errorMsg);
      }
      
      // Fetch sessioni
      const sessionsRes = await api.getSessionsRange(startDate, endDate);
      if (sessionsRes.data.success) {
        setSessionsData(sessionsRes.data.data);
        setSessionsMeta(sessionsRes.data.meta);
      }
    } catch (err) {
      console.error('Failed to fetch data', err);
      const errorMsg = 'Impossibile caricare i dati. Verifica che il backend sia attivo.';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
      setLoadingSessions(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [startDate, endDate]);

  // Trasforma i dati per Recharts
  const chartData = useMemo(() => {
    return data.map(item => {
      const dateObj = parseISO(item.date);
      const formattedDate = format(dateObj, 'dd/MM', { locale: it });
      const dayName = format(dateObj, 'EEE', { locale: it });
      
      return {
        date: formattedDate,
        fullDate: item.date,
        dayName: dayName,
        swi: item.swi,
        isWeekend: item.isWeekend
      };
    });
  }, [data]);

  // Preset per selezione rapida date
  const datePresets = [
    { label: 'Ultimi 7 giorni', days: 7 },
    { label: 'Ultimi 14 giorni', days: 14 },
    { label: 'Ultimi 30 giorni', days: 30 },
    { label: 'Ultimi 45 giorni', days: 45 },
    { label: 'Ultimi 60 giorni', days: 60 },
  ];

  const applyPreset = (days) => {
    const end = subDays(new Date(), 1);
    const start = subDays(end, days - 1);
    setEndDate(format(end, 'yyyy-MM-dd'));
    setStartDate(format(start, 'yyyy-MM-dd'));
  };

  // Custom tooltip component
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null;
    
    const dataPoint = payload[0]?.payload;
    if (!dataPoint) return null;

    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 min-w-[160px]">
        <p className="text-sm font-medium text-gray-900">
          {dataPoint.fullDate}
        </p>
        <p className="text-xs text-gray-500 capitalize mb-2">
          {dataPoint.dayName} {dataPoint.isWeekend && '(Weekend)'}
        </p>
        <p className={`text-lg font-bold ${dataPoint.isWeekend ? 'text-violet-600' : 'text-blue-600'}`}>
          {dataPoint.swi?.toLocaleString('it-IT')} SWI
        </p>
      </div>
    );
  };

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <TrendingUp className="text-blue-600" size={28} />
          Dashboard SWI
        </h2>
        <p className="text-gray-500 mt-1">
          Andamento delle conversioni SWI nel tempo
        </p>
      </div>

      {/* Controls */}
      <Card className="mb-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          {/* Date Inputs */}
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Calendar size={18} className="text-gray-400" aria-hidden="true" />
              <label htmlFor="start-date" className="text-sm text-gray-600">Da:</label>
              <input
                id="start-date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                aria-label="Data inizio periodo"
              />
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="end-date" className="text-sm text-gray-600">A:</label>
              <input
                id="end-date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                aria-label="Data fine periodo"
              />
            </div>
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
              aria-label="Aggiorna grafici con nuove date"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} aria-hidden="true" />
              Aggiorna
            </button>
          </div>

          {/* Quick Presets */}
          <div className="flex flex-wrap gap-2" role="group" aria-label="Presets periodo rapido">
            {datePresets.map((preset) => (
              <button
                key={preset.days}
                onClick={() => applyPreset(preset.days)}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
                aria-label={`Seleziona ${preset.label.toLowerCase()}`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Stats Summary */}
      {meta && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Card decoration="top" decorationColor="blue">
            <Text>Media Periodo</Text>
            <Title className="text-2xl">{meta.average?.toLocaleString('it-IT')}</Title>
          </Card>
          <Card decoration="top" decorationColor="emerald">
            <Text>Giorni Analizzati</Text>
            <Title className="text-2xl">{meta.count}</Title>
          </Card>
          <Card decoration="top" decorationColor="violet">
            <Text>Periodo</Text>
            <Title className="text-lg">
              {format(parseISO(meta.start_date), 'dd MMM', { locale: it })} - {format(parseISO(meta.end_date), 'dd MMM yyyy', { locale: it })}
            </Title>
          </Card>
        </div>
      )}

      {/* SWI Chart - Grafico principale */}
      <Card className="mb-6">
        <Title>Conversioni SWI per Giorno</Title>
        <Text className="mb-4">
          <span className="inline-flex items-center gap-2">
            <span className="w-3 h-3 rounded" style={{ backgroundColor: COLORS.weekday }}></span> Giorni feriali
            <span className="w-3 h-3 rounded ml-3" style={{ backgroundColor: COLORS.weekend }}></span> Weekend
            <span className="w-8 h-0.5 ml-3" style={{ backgroundColor: COLORS.average }}></span> Media periodo
          </span>
        </Text>

        {loading ? (
          <div className="h-80 flex items-center justify-center">
            <RefreshCw size={32} className="text-gray-400 animate-spin" />
          </div>
        ) : error ? (
          <div className="h-80 flex items-center justify-center">
            <div className="text-center">
              <p className="text-red-500 font-medium">{error}</p>
              <button
                onClick={fetchData}
                className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm"
              >
                Riprova
              </button>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
              <XAxis 
                dataKey="date" 
                tick={{ fontSize: 11, fill: '#6b7280' }}
                tickLine={false}
                axisLine={{ stroke: '#e5e7eb' }}
                interval="preserveStartEnd"
              />
              <YAxis 
                tick={{ fontSize: 11, fill: '#6b7280' }}
                tickLine={false}
                axisLine={false}
                width={50}
              />
              <Tooltip content={<CustomTooltip />} />
              
              {/* Reference line for average */}
              {meta && (
                <ReferenceLine 
                  y={meta.average} 
                  stroke={COLORS.average}
                  strokeDasharray="5 5"
                  strokeWidth={2}
                  label={{
                    value: `Media: ${meta.average}`,
                    position: 'right',
                    fill: COLORS.average,
                    fontSize: 11,
                    fontWeight: 500
                  }}
                />
              )}
              
              {/* Bars with conditional coloring */}
              <Bar dataKey="swi" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`}
                    fill={entry.isWeekend ? COLORS.weekend : COLORS.weekday}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Sessions Charts - Affiancati sotto il grafico SWI */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <SessionsChart 
          title="Sessioni Commodity"
          dataKey="commodity"
          totals={sessionsData.totals}
          byChannel={sessionsData.by_channel}
          loading={loadingSessions}
          channels={sessionsMeta?.channels || []}
        />
        <SessionsChart 
          title="Sessioni Luce & Gas"
          dataKey="lucegas"
          totals={sessionsData.totals}
          byChannel={sessionsData.by_channel}
          loading={loadingSessions}
          channels={sessionsMeta?.channels || []}
        />
      </div>

      {/* Footer info */}
      <div className="mt-4 text-center text-sm text-gray-400">
        I dati vengono aggiornati quotidianamente. Ultimo aggiornamento disponibile: {meta?.end_date}
      </div>
    </main>
  );
}

