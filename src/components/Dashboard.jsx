import React, { useState, useEffect, useMemo, useCallback, memo } from 'react';
import { Card, Title, Text } from './ui/Card';
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
  ReferenceArea,
  Cell
} from 'recharts';
import promoCalendar from '../data/promoCalendar.json';
import { format, subDays, parseISO } from 'date-fns';
import { it } from 'date-fns/locale';
import { api } from '../services/api';
import { logError } from '../utils/logger';
import {
  getFromCache,
  setInCache,
  getMetricsCacheKey,
  getSessionsCacheKey,
  CACHE_TTL
} from '../utils/cache';
import { Calendar, RefreshCw, TrendingUp } from 'lucide-react';
import { SessionsChart } from './SessionsChart';
import { CRChart } from './CRChart';

// Colori per il grafico - definiti fuori dal componente
const COLORS = {
  weekday: '#3b82f6',  // blue-500
  weekend: '#8b5cf6',  // violet-500
  average: '#ef4444',  // red-500
};

// Colori per tipologia promozione
const PROMO_COLORS = {
  'Operazione a premio': '#f59e0b',  // amber-500
  'Promo': '#10b981',                // emerald-500
  'Prodotto': '#8b5cf6',             // violet-500
};

/**
 * Filtra le promozioni attive in un dato range di date
 * @param {string} rangeStart - Data inizio range (YYYY-MM-DD)
 * @param {string} rangeEnd - Data fine range (YYYY-MM-DD)
 * @returns {Array} - Promozioni che si sovrappongono al range
 */
const getActivePromos = (rangeStart, rangeEnd) => {
  if (!rangeStart || !rangeEnd) return [];
  
  const rangeStartDate = parseISO(rangeStart);
  const rangeEndDate = parseISO(rangeEnd);
  
  return promoCalendar.promos.filter(promo => {
    const promoStart = parseISO(promo.startDate);
    const promoEnd = parseISO(promo.endDate);
    
    // La promo si sovrappone al range se:
    // promoStart <= rangeEnd AND promoEnd >= rangeStart
    return promoStart <= rangeEndDate && promoEnd >= rangeStartDate;
  }).map(promo => {
    // Calcola le date effettive da mostrare (clip al range visualizzato)
    const promoStart = parseISO(promo.startDate);
    const promoEnd = parseISO(promo.endDate);
    
    const effectiveStart = promoStart < rangeStartDate ? rangeStartDate : promoStart;
    const effectiveEnd = promoEnd > rangeEndDate ? rangeEndDate : promoEnd;
    
    return {
      ...promo,
      effectiveStartDate: format(effectiveStart, 'dd/MM', { locale: it }),
      effectiveEndDate: format(effectiveEnd, 'dd/MM', { locale: it }),
      color: PROMO_COLORS[promo.type] || '#9ca3af'  // gray-400 fallback
    };
  });
};

// Preset per selezione rapida date - definiti fuori dal componente
const DATE_PRESETS = [
  { label: 'Ultimi 7 giorni', days: 7 },
  { label: 'Ultimi 14 giorni', days: 14 },
  { label: 'Ultimi 30 giorni', days: 30 },
  { label: 'Ultimi 45 giorni', days: 45 },
  { label: 'Ultimi 60 giorni', days: 60 },
];

/**
 * Trova le promozioni attive per una data specifica
 * @param {string} dateStr - Data in formato YYYY-MM-DD
 * @returns {Array} - Promozioni attive per quella data
 */
const getPromosForDate = (dateStr) => {
  if (!dateStr) return [];
  const date = parseISO(dateStr);
  
  return promoCalendar.promos.filter(promo => {
    const promoStart = parseISO(promo.startDate);
    const promoEnd = parseISO(promo.endDate);
    return date >= promoStart && date <= promoEnd;
  });
};

/**
 * Custom tooltip component - memoized
 * Mostra anche le promozioni attive per la data selezionata
 */
const CustomTooltip = memo(({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;

  const dataPoint = payload[0]?.payload;
  if (!dataPoint) return null;

  // Trova promozioni attive per questa data
  const activePromosForDate = getPromosForDate(dataPoint.fullDate);

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 min-w-[180px]">
      <p className="text-sm font-medium text-gray-900">
        {dataPoint.fullDate}
      </p>
      <p className="text-xs text-gray-500 capitalize mb-2">
        {dataPoint.dayName} {dataPoint.isWeekend && '(Weekend)'}
      </p>
      <p className={`text-lg font-bold ${dataPoint.isWeekend ? 'text-violet-600' : 'text-blue-600'}`}>
        {dataPoint.swi?.toLocaleString('it-IT')} SWI
      </p>
      
      {/* Mostra promozioni attive */}
      {activePromosForDate.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-100">
          <p className="text-xs text-gray-500 mb-1">Promo attive:</p>
          {activePromosForDate.map((promo, idx) => (
            <div key={idx} className="flex items-center gap-1.5 text-xs">
              <span 
                className="w-2 h-2 rounded-full flex-shrink-0" 
                style={{ backgroundColor: PROMO_COLORS[promo.type] || '#9ca3af' }}
              />
              <span className="font-medium text-gray-700">{promo.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

CustomTooltip.displayName = 'CustomTooltip';

/**
 * Stats summary cards - memoized
 */
const StatsSummary = memo(({ meta }) => {
  if (!meta) return null;

  return (
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
  );
});

StatsSummary.displayName = 'StatsSummary';

/**
 * Date preset button - memoized
 */
const PresetButton = memo(({ label, days, onClick }) => (
  <button
    onClick={() => onClick(days)}
    className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
    aria-label={`Seleziona ${label.toLowerCase()}`}
  >
    {label}
  </button>
));

PresetButton.displayName = 'PresetButton';

/**
 * Main Dashboard component
 */
function DashboardComponent() {
  const [data, setData] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Sessions data
  const [sessionsData, setSessionsData] = useState({ totals: [], by_channel: [] });
  const [sessionsMeta, setSessionsMeta] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(true);

  // Date range state (default: ultimi 45 giorni)
  const [endDate, setEndDate] = useState(() => format(subDays(new Date(), 1), 'yyyy-MM-dd'));
  const [startDate, setStartDate] = useState(() => format(subDays(new Date(), 45), 'yyyy-MM-dd'));

  // Fetch data with caching - memoized
  const fetchData = useCallback(async (forceRefresh = false) => {
    const metricsCacheKey = getMetricsCacheKey(startDate, endDate);
    const sessionsCacheKey = getSessionsCacheKey(startDate, endDate);

    // Check cache first (unless force refresh)
    if (!forceRefresh) {
      const cachedMetrics = getFromCache(metricsCacheKey);
      const cachedSessions = getFromCache(sessionsCacheKey);

      if (cachedMetrics && cachedSessions) {
        setData(cachedMetrics.data);
        setMeta(cachedMetrics.meta);
        setSessionsData(cachedSessions.data);
        setSessionsMeta(cachedSessions.meta);
        setLoading(false);
        setLoadingSessions(false);
        return;
      }
    }

    setLoading(true);
    setLoadingSessions(true);
    setError(null);

    try {
      // Fetch metriche SWI
      const metricsRes = await api.getMetricsRange(startDate, endDate);
      if (metricsRes.data.success) {
        setData(metricsRes.data.data);
        setMeta(metricsRes.data.meta);
        // Cache the result
        setInCache(metricsCacheKey, {
          data: metricsRes.data.data,
          meta: metricsRes.data.meta
        }, CACHE_TTL.METRICS);
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
        // Cache the result
        setInCache(sessionsCacheKey, {
          data: sessionsRes.data.data,
          meta: sessionsRes.data.meta
        }, CACHE_TTL.SESSIONS);
      }
    } catch (err) {
      logError('Failed to fetch data', err);
      const errorMsg = 'Impossibile caricare i dati. Verifica che il backend sia attivo.';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
      setLoadingSessions(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Trasforma i dati per Recharts - memoized
  const chartData = useMemo(() => {
    return data.map(item => {
      const dateObj = parseISO(item.date);
      return {
        date: format(dateObj, 'dd/MM', { locale: it }),
        fullDate: item.date,
        dayName: format(dateObj, 'EEE', { locale: it }),
        swi: item.swi,
        isWeekend: item.isWeekend
      };
    });
  }, [data]);

  // Apply preset - memoized
  const applyPreset = useCallback((days) => {
    const end = subDays(new Date(), 1);
    const start = subDays(end, days - 1);
    setEndDate(format(end, 'yyyy-MM-dd'));
    setStartDate(format(start, 'yyyy-MM-dd'));
  }, []);

  // Force refresh handler
  const handleRefresh = useCallback(() => {
    fetchData(true);
  }, [fetchData]);

  // Memoized channels array
  const channels = useMemo(() => sessionsMeta?.channels || [], [sessionsMeta]);

  // Promozioni attive nel range visualizzato
  const activePromos = useMemo(() => {
    return getActivePromos(startDate, endDate);
  }, [startDate, endDate]);

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
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                aria-label="Data fine periodo"
              />
            </div>
            <button
              onClick={handleRefresh}
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
            {DATE_PRESETS.map((preset) => (
              <PresetButton
                key={preset.days}
                label={preset.label}
                days={preset.days}
                onClick={applyPreset}
              />
            ))}
          </div>
        </div>
      </Card>

      {/* Stats Summary */}
      <StatsSummary meta={meta} />

      {/* SWI Chart - Grafico principale */}
      <Card className="mb-6">
        <Title>Conversioni SWI per Giorno</Title>
        <Text className="mb-4">
          <span className="inline-flex items-center gap-2 flex-wrap">
            <span className="w-3 h-3 rounded" style={{ backgroundColor: COLORS.weekday }}></span> Giorni feriali
            <span className="w-3 h-3 rounded ml-3" style={{ backgroundColor: COLORS.weekend }}></span> Weekend
            <span className="w-8 h-0.5 ml-3" style={{ backgroundColor: COLORS.average }}></span> Media periodo
            {/* Separatore visivo */}
            <span className="mx-2 text-gray-300">|</span>
            {/* Legenda promozioni */}
            <span className="text-gray-500 text-xs">Promo:</span>
            <span className="w-3 h-3 rounded opacity-60" style={{ backgroundColor: PROMO_COLORS['Operazione a premio'] }}></span>
            <span className="text-xs">Op. a premio</span>
            <span className="w-3 h-3 rounded ml-2 opacity-60" style={{ backgroundColor: PROMO_COLORS['Promo'] }}></span>
            <span className="text-xs">Promo</span>
            <span className="w-3 h-3 rounded ml-2 opacity-60" style={{ backgroundColor: PROMO_COLORS['Prodotto'] }}></span>
            <span className="text-xs">Prodotto</span>
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
                onClick={handleRefresh}
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
              
              {/* Reference areas per promozioni attive - renderizzate sullo sfondo */}
              {activePromos.map((promo, index) => (
                <ReferenceArea
                  key={`promo-${index}-${promo.name}`}
                  x1={promo.effectiveStartDate}
                  x2={promo.effectiveEndDate}
                  fill={promo.color}
                  fillOpacity={0.15}
                  strokeOpacity={0}
                />
              ))}
              
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
          channels={channels}
        />
        <SessionsChart
          title="Sessioni Luce & Gas"
          dataKey="lucegas"
          totals={sessionsData.totals}
          byChannel={sessionsData.by_channel}
          loading={loadingSessions}
          channels={channels}
        />
      </div>

      {/* CR Charts - Grafici Conversion Rate */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <CRChart
          title="CR Commodity"
          dataKey="cr_commodity"
          data={data}
          average={meta?.avg_cr_commodity}
          loading={loading}
        />
        <CRChart
          title="CR Luce & Gas"
          dataKey="cr_lucegas"
          data={data}
          average={meta?.avg_cr_lucegas}
          loading={loading}
        />
      </div>

      {/* Footer info */}
      <div className="mt-4 text-center text-sm text-gray-400">
        I dati vengono aggiornati quotidianamente. Ultimo aggiornamento disponibile: {meta?.end_date}
      </div>
    </main>
  );
}

// Export memoized component
export const Dashboard = memo(DashboardComponent);

Dashboard.displayName = 'Dashboard';
