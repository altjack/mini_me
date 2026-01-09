import React, { useState, useMemo, useCallback, memo } from 'react';
import { Card, Title, Text } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Skeleton } from './ui/Skeleton';
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
import campaignCalendar from '../data/campaignCalendar.json';
import { format, subDays, parseISO } from 'date-fns';
import { it } from 'date-fns/locale';
import { TrendingUp, RefreshCw, Calendar as CalendarIcon } from 'lucide-react';
import { SessionsChart } from './SessionsChart';
import { CRChart } from './CRChart';
import { useDashboardMetrics, useDashboardSessions, DATE_PRESETS } from '../hooks/useDashboardData';

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

// Colore per linee campagne commerciali
const CAMPAIGN_COLOR = '#000000';  // black

/**
 * Filtra le promozioni attive in un dato range di date
 */
const getActivePromos = (rangeStart, rangeEnd) => {
  if (!rangeStart || !rangeEnd) return [];
  
  const rangeStartDate = parseISO(rangeStart);
  const rangeEndDate = parseISO(rangeEnd);
  
  return promoCalendar.promos.filter(promo => {
    const promoStart = parseISO(promo.startDate);
    const promoEnd = parseISO(promo.endDate);
    return promoStart <= rangeEndDate && promoEnd >= rangeStartDate;
  }).map(promo => {
    const promoStart = parseISO(promo.startDate);
    const promoEnd = parseISO(promo.endDate);
    
    const effectiveStart = promoStart < rangeStartDate ? rangeStartDate : promoStart;
    const effectiveEnd = promoEnd > rangeEndDate ? rangeEndDate : promoEnd;
    
    return {
      ...promo,
      effectiveStartDate: format(effectiveStart, 'dd/MM', { locale: it }),
      effectiveEndDate: format(effectiveEnd, 'dd/MM', { locale: it }),
      color: PROMO_COLORS[promo.type] || '#9ca3af'
    };
  });
};

/**
 * Trova le date di inizio campagne commerciali visibili nel range
 */
const getCampaignStartsInRange = (rangeStart, rangeEnd) => {
  if (!rangeStart || !rangeEnd) return [];

  const rangeStartDate = parseISO(rangeStart);
  const rangeEndDate = parseISO(rangeEnd);

  return campaignCalendar.campaigns.filter(campaign => {
    const campaignStart = parseISO(campaign.startDate);
    return campaignStart >= rangeStartDate && campaignStart <= rangeEndDate;
  }).map(campaign => ({
    ...campaign,
    displayDate: format(parseISO(campaign.startDate), 'dd/MM', { locale: it })
  }));
};

/**
 * Trova la campagna commerciale attiva per una data specifica
 */
const getCampaignForDate = (dateStr) => {
  if (!dateStr) return null;
  const date = parseISO(dateStr);

  return campaignCalendar.campaigns.find(campaign => {
    const campaignStart = parseISO(campaign.startDate);
    const campaignEnd = parseISO(campaign.endDate);
    return date >= campaignStart && date <= campaignEnd;
  }) || null;
};

/**
 * Trova le promozioni attive per una data specifica
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

const CustomTooltip = memo(({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;

  const dataPoint = payload[0]?.payload;
  if (!dataPoint) return null;

  const activePromosForDate = getPromosForDate(dataPoint.fullDate);
  const activeCampaign = getCampaignForDate(dataPoint.fullDate);

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

      {activeCampaign && (
        <div className="mt-2 pt-2 border-t border-gray-100">
          <p className="text-xs text-gray-500 mb-1">Campagna commerciale:</p>
          <div className="flex items-center gap-1.5 text-xs">
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: CAMPAIGN_COLOR }}
            />
            <span className="font-medium text-gray-700">{activeCampaign.name}</span>
          </div>
        </div>
      )}

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

const StatsSummary = memo(({ meta, loading }) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    );
  }

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

const PresetButton = memo(({ label, days, onClick }) => (
  <Button
    variant="secondary"
    size="sm"
    onClick={() => onClick(days)}
    className="text-xs"
  >
    {label}
  </Button>
));

PresetButton.displayName = 'PresetButton';

function DashboardComponent() {
  // Date range state (default: ultimi 45 giorni)
  const [endDate, setEndDate] = useState(() => format(subDays(new Date(), 1), 'yyyy-MM-dd'));
  const [startDate, setStartDate] = useState(() => format(subDays(new Date(), 45), 'yyyy-MM-dd'));

  // Custom hooks for data fetching
  const { 
    data: metricsResponse, 
    isLoading: loadingMetrics, 
    error: metricsError,
    refetch: refetchMetrics
  } = useDashboardMetrics(startDate, endDate);

  const { 
    data: sessionsResponse, 
    isLoading: loadingSessions,
    error: sessionsError,
    refetch: refetchSessions
  } = useDashboardSessions(startDate, endDate);

  // Extract data from responses
  const data = useMemo(() => metricsResponse?.data || [], [metricsResponse]);
  const meta = metricsResponse?.meta;
  const sessionsData = sessionsResponse?.data || { totals: [], by_channel: [] };
  const sessionsMeta = sessionsResponse?.meta;

  const loading = loadingMetrics; // Main loading state for metrics
  const error = metricsError ? metricsError.message : (sessionsError ? sessionsError.message : null);

  // Effect for error toast
  if (error) {
    // We use a toast only once per error instance ideally, but since we are rendering, avoid side-effects here ideally.
    // However, the original code used toast.error inside fetchData.
    // Here we can rely on the UI displaying the error, or use a useEffect.
    // Let's stick to UI display for error, maybe a toast in useEffect if error changes.
  }

  // Apply preset
  const applyPreset = useCallback((days) => {
    const end = subDays(new Date(), 1);
    const start = subDays(end, days - 1);
    setEndDate(format(end, 'yyyy-MM-dd'));
    setStartDate(format(start, 'yyyy-MM-dd'));
  }, []);

  // Force refresh handler
  const handleRefresh = useCallback(() => {
    refetchMetrics();
    refetchSessions();
  }, [refetchMetrics, refetchSessions]);

  // Transform data for Recharts
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

  const channels = useMemo(() => sessionsMeta?.channels || [], [sessionsMeta]);
  const campaigns = useMemo(() => sessionsMeta?.campaigns || [], [sessionsMeta]);

  const activePromos = useMemo(() => {
    return getActivePromos(startDate, endDate);
  }, [startDate, endDate]);

  const campaignStarts = useMemo(() => {
    return getCampaignStartsInRange(startDate, endDate);
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
            <div className="w-40">
              <Input
                type="date"
                label="Da"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="w-40">
              <Input
                type="date"
                label="A"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
            <div className="flex items-end h-full pb-0.5">
              <Button
                onClick={handleRefresh}
                isLoading={loading || loadingSessions}
              >
                {!loading && !loadingSessions && <RefreshCw size={16} className="mr-2" />}
                Aggiorna
              </Button>
            </div>
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
      <StatsSummary meta={meta} loading={loading} />

      {/* SWI Chart - Grafico principale */}
      <Card className="mb-6">
        <Title>Conversioni SWI per Giorno</Title>
        <Text className="mb-4">
          <span className="inline-flex items-center gap-2 flex-wrap">
            <span className="w-3 h-3 rounded" style={{ backgroundColor: COLORS.weekday }}></span> Giorni feriali
            <span className="w-3 h-3 rounded ml-3" style={{ backgroundColor: COLORS.weekend }}></span> Weekend
            <span className="w-8 h-0.5 ml-3" style={{ backgroundColor: COLORS.average }}></span> Media periodo
            <span className="mx-2 text-gray-300">|</span>
            <span className="w-0.5 h-4 ml-1" style={{ backgroundColor: CAMPAIGN_COLOR }}></span>
            <span className="text-xs">Cambio campagna</span>
            <span className="mx-2 text-gray-300">|</span>
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
          <div className="h-80 w-full">
            <Skeleton className="h-full w-full" />
          </div>
        ) : error ? (
          <div className="h-80 flex items-center justify-center">
            <div className="text-center">
              <p className="text-red-500 font-medium">{error}</p>
              <Button
                onClick={handleRefresh}
                variant="primary"
                className="mt-4"
              >
                Riprova
              </Button>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
              
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

              {campaignStarts.map((campaign, index) => (
                <ReferenceLine
                  key={`campaign-${index}-${campaign.name}`}
                  x={campaign.displayDate}
                  stroke={CAMPAIGN_COLOR}
                  strokeWidth={2}
                  label={{
                    value: campaign.name,
                    position: 'top',
                    fill: CAMPAIGN_COLOR,
                    fontSize: 10,
                    fontWeight: 600
                  }}
                />
              ))}

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

      {/* Sessions Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <SessionsChart
          title="Sessioni Commodity"
          dataKey="commodity"
          totals={sessionsData.totals}
          byChannel={sessionsData.by_channel}
          byCampaign={sessionsData.by_campaign || []}
          loading={loadingSessions}
          channels={channels}
          campaigns={campaigns}
        />
        <SessionsChart
          title="Sessioni Luce & Gas"
          dataKey="lucegas"
          totals={sessionsData.totals}
          byChannel={sessionsData.by_channel}
          byCampaign={sessionsData.by_campaign || []}
          loading={loadingSessions}
          channels={channels}
          campaigns={campaigns}
        />
      </div>

      {/* CR Charts */}
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

export const Dashboard = memo(DashboardComponent);
Dashboard.displayName = 'Dashboard';
