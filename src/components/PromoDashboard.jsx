import React, { useState, useEffect, useMemo, useCallback, memo, useRef } from 'react';
import { Card, Title, Text } from './ui/Card';
import toast from 'react-hot-toast';
import { format, subDays, parseISO, differenceInDays } from 'date-fns';
import { it } from 'date-fns/locale';
import { api } from '../services/api';
import { logError } from '../utils/logger';
import { usePromo } from '../context/PromoContext';
import promoCalendar from '../data/promoCalendar.json';
import { Calendar, RefreshCw, TrendingUp, TrendingDown, Gift, ArrowRight } from 'lucide-react';

// =============================================================================
// TYPES & CONSTANTS
// =============================================================================

const PROMO_TYPE_COLORS = {
  'Operazione a premio': 'bg-amber-100 text-amber-800 border-amber-200',
  'Promo': 'bg-emerald-100 text-emerald-800 border-emerald-200',
  'Prodotto': 'bg-violet-100 text-violet-800 border-violet-200',
};

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Calcola la variazione percentuale tra due valori
 * @returns {number|null} Percentuale di variazione o null se non calcolabile
 */
const calculateChange = (current, previous) => {
  if (previous === null || previous === undefined || previous === 0) return null;
  if (current === null || current === undefined) return null;
  return ((current - previous) / previous) * 100;
};

/**
 * Formatta un numero con separatore migliaia italiano
 */
const formatNumber = (num, decimals = 0) => {
  if (num === null || num === undefined) return '-';
  return num.toLocaleString('it-IT', { 
    minimumFractionDigits: decimals, 
    maximumFractionDigits: decimals 
  });
};

/**
 * Calcola il periodo di confronto di default (stesso numero di giorni prima della promo)
 */
const getDefaultComparisonDates = (promoStart, promoEnd) => {
  if (!promoStart || !promoEnd) return { start: null, end: null };
  
  const start = parseISO(promoStart);
  const end = parseISO(promoEnd);
  const days = differenceInDays(end, start) + 1; // +1 perché inclusivo
  
  // Periodo di confronto: stessi giorni immediatamente prima
  const compEnd = subDays(start, 1);
  const compStart = subDays(compEnd, days - 1);
  
  return {
    start: format(compStart, 'yyyy-MM-dd'),
    end: format(compEnd, 'yyyy-MM-dd')
  };
};

// =============================================================================
// KPI WIDGET COMPONENT
// =============================================================================

const KPIWidget = memo(({ 
  title, 
  value, 
  comparisonValue, 
  change, 
  unit = '',
  loading = false,
  decorationColor = 'blue'
}) => {
  const isPositive = change !== null && change >= 0;
  const changeColor = isPositive ? 'text-emerald-600' : 'text-red-600';
  const ChangeTrendIcon = isPositive ? TrendingUp : TrendingDown;

  return (
    <Card decoration="top" decorationColor={decorationColor} className="relative">
      {loading && (
        <div className="absolute inset-0 bg-white/70 flex items-center justify-center rounded-xl z-10">
          <RefreshCw size={24} className="text-gray-400 animate-spin" />
        </div>
      )}
      
      <Text className="text-gray-500 font-medium mb-1">{title}</Text>
      
      <div className="mt-2">
        <Title className="text-3xl font-bold text-gray-900">
          {value !== null ? `${formatNumber(value, unit === '%' ? 2 : 0)}${unit}` : '-'}
        </Title>
        
        {change !== null && (
          <div className={`flex items-center gap-1.5 mt-2 ${changeColor}`}>
            <ChangeTrendIcon size={18} />
            <span className="font-semibold">
              {change >= 0 ? '+' : ''}{formatNumber(change, 1)}%
            </span>
            <span className="text-gray-400 text-sm ml-1">vs confronto</span>
          </div>
        )}
        
        {comparisonValue !== null && (
          <Text className="mt-1 text-xs text-gray-400">
            Confronto: {formatNumber(comparisonValue, unit === '%' ? 2 : 0)}{unit}
          </Text>
        )}
      </div>
    </Card>
  );
});

KPIWidget.displayName = 'KPIWidget';

// =============================================================================
// PROMO SELECTOR COMPONENT
// =============================================================================

const PromoSelector = memo(({ selectedPromo, onSelect, promos }) => {
  // Ordina promo per data (più recenti prima)
  const sortedPromos = useMemo(() => {
    return [...promos].sort((a, b) => 
      new Date(b.startDate) - new Date(a.startDate)
    );
  }, [promos]);

  // Usa index come valore per evitare problemi con parsing
  const handleChange = useCallback((e) => {
    const idx = parseInt(e.target.value, 10);
    if (isNaN(idx) || idx < 0) {
      onSelect(null);
    } else {
      onSelect(sortedPromos[idx] || null);
    }
  }, [sortedPromos, onSelect]);

  // Trova indice della promo selezionata
  const selectedIndex = selectedPromo 
    ? sortedPromos.findIndex(p => p.name === selectedPromo.name && p.startDate === selectedPromo.startDate)
    : -1;

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor="promo-select" className="text-sm font-medium text-gray-700 flex items-center gap-2">
        <Gift size={16} className="text-amber-500" />
        Seleziona Promozione
      </label>
      <select
        id="promo-select"
        value={selectedIndex >= 0 ? selectedIndex : ''}
        onChange={handleChange}
        className="px-4 py-2.5 border border-gray-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 cursor-pointer"
      >
        <option value="">-- Seleziona una promo --</option>
        {sortedPromos.map((promo, idx) => (
          <option 
            key={`${promo.name}-${promo.startDate}-${idx}`} 
            value={idx}
          >
            {promo.name} ({format(parseISO(promo.startDate), 'dd MMM', { locale: it })} - {format(parseISO(promo.endDate), 'dd MMM yyyy', { locale: it })})
          </option>
        ))}
      </select>
      
      {selectedPromo && (
        <div className="flex items-center gap-2 mt-1">
          <span className={`text-xs px-2 py-0.5 rounded-full border ${PROMO_TYPE_COLORS[selectedPromo.type] || 'bg-gray-100 text-gray-700'}`}>
            {selectedPromo.type}
          </span>
          <span className="text-xs text-gray-500">
            {differenceInDays(parseISO(selectedPromo.endDate), parseISO(selectedPromo.startDate)) + 1} giorni
          </span>
        </div>
      )}
    </div>
  );
});

PromoSelector.displayName = 'PromoSelector';

// =============================================================================
// MAIN COMPONENT
// =============================================================================

function PromoDashboardComponent() {
  // Global state from context (persists between page changes)
  const {
    selectedPromo,
    setSelectedPromo,
    compStartDate,
    setCompStartDate,
    compEndDate,
    setCompEndDate,
  } = usePromo();

  // Local state: Data (fetched on mount/change)
  const [promoData, setPromoData] = useState(null);
  const [comparisonData, setComparisonData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Track previous promo to detect actual changes
  const prevPromoRef = useRef(selectedPromo);

  // Update comparison dates only when promo actually changes (not on mount with existing selection)
  useEffect(() => {
    const prevPromo = prevPromoRef.current;
    const promoChanged = selectedPromo?.name !== prevPromo?.name ||
                         selectedPromo?.startDate !== prevPromo?.startDate;

    if (selectedPromo && promoChanged) {
      // Promo changed - calculate default comparison dates
      const defaults = getDefaultComparisonDates(selectedPromo.startDate, selectedPromo.endDate);
      setCompStartDate(defaults.start || '');
      setCompEndDate(defaults.end || '');
    } else if (!selectedPromo) {
      // Promo deselected - clear dates
      setCompStartDate('');
      setCompEndDate('');
    }
    // If promo exists and didn't change, keep existing dates (user edited them)

    prevPromoRef.current = selectedPromo;
  }, [selectedPromo, setCompStartDate, setCompEndDate]);

  // Fetch data when promo or comparison dates change
  const fetchData = useCallback(async () => {
    if (!selectedPromo || !compStartDate || !compEndDate) {
      setPromoData(null);
      setComparisonData(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Fetch both periods in parallel
      const [promoRes, compRes] = await Promise.all([
        api.getMetricsRange(selectedPromo.startDate, selectedPromo.endDate),
        api.getMetricsRange(compStartDate, compEndDate)
      ]);

      if (promoRes.data.success) {
        setPromoData(promoRes.data);
      } else {
        throw new Error(promoRes.data.error || 'Errore caricamento dati promo');
      }

      if (compRes.data.success) {
        setComparisonData(compRes.data);
      } else {
        throw new Error(compRes.data.error || 'Errore caricamento dati confronto');
      }
    } catch (err) {
      logError('Failed to fetch promo data', err);
      setError(err.message || 'Impossibile caricare i dati');
      toast.error('Errore nel caricamento dei dati');
    } finally {
      setLoading(false);
    }
  }, [selectedPromo, compStartDate, compEndDate]);

  // Auto-fetch when dates change
  useEffect(() => {
    if (selectedPromo && compStartDate && compEndDate) {
      fetchData();
    }
  }, [fetchData, selectedPromo, compStartDate, compEndDate]);

  // Calculate KPIs
  const kpis = useMemo(() => {
    if (!promoData?.data || !comparisonData?.data) {
      return { swi: null, crCommodity: null, crLucegas: null };
    }

    // SWI: somma totale
    const promoSwi = promoData.data.reduce((sum, d) => sum + (d.swi || 0), 0);
    const compSwi = comparisonData.data.reduce((sum, d) => sum + (d.swi || 0), 0);

    // CR Commodity: media
    const promoCrCommodity = promoData.meta?.avg_cr_commodity || 0;
    const compCrCommodity = comparisonData.meta?.avg_cr_commodity || 0;

    // CR Luce e Gas: media
    const promoCrLucegas = promoData.meta?.avg_cr_lucegas || 0;
    const compCrLucegas = comparisonData.meta?.avg_cr_lucegas || 0;

    return {
      swi: {
        value: promoSwi,
        comparison: compSwi,
        change: calculateChange(promoSwi, compSwi)
      },
      crCommodity: {
        value: promoCrCommodity,
        comparison: compCrCommodity,
        change: calculateChange(promoCrCommodity, compCrCommodity)
      },
      crLucegas: {
        value: promoCrLucegas,
        comparison: compCrLucegas,
        change: calculateChange(promoCrLucegas, compCrLucegas)
      }
    };
  }, [promoData, comparisonData]);

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Gift className="text-amber-500" size={28} />
          Analisi Promozioni
        </h2>
        <p className="text-gray-500 mt-1">
          Confronta le performance delle promozioni con periodi di riferimento
        </p>
      </div>

      {/* Controls */}
      <Card className="mb-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Promo Selector */}
          <PromoSelector
            selectedPromo={selectedPromo}
            onSelect={setSelectedPromo}
            promos={promoCalendar.promos}
          />

          {/* Comparison Date Range */}
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
              <Calendar size={16} className="text-blue-500" />
              Periodo di Confronto
            </label>
            <div className="flex items-center gap-3">
              <input
                type="date"
                value={compStartDate}
                onChange={(e) => setCompStartDate(e.target.value)}
                disabled={!selectedPromo}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
                aria-label="Data inizio confronto"
              />
              <ArrowRight size={18} className="text-gray-400 flex-shrink-0" />
              <input
                type="date"
                value={compEndDate}
                onChange={(e) => setCompEndDate(e.target.value)}
                disabled={!selectedPromo}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
                aria-label="Data fine confronto"
              />
              <button
                onClick={fetchData}
                disabled={loading || !selectedPromo}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Aggiorna dati"
              >
                <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                Aggiorna
              </button>
            </div>
            {selectedPromo && compStartDate && compEndDate && (
              <Text className="text-xs text-gray-400 mt-1">
                Confronto: {format(parseISO(compStartDate), 'dd MMM', { locale: it })} - {format(parseISO(compEndDate), 'dd MMM yyyy', { locale: it })}
                {' '}({differenceInDays(parseISO(compEndDate), parseISO(compStartDate)) + 1} giorni)
              </Text>
            )}
          </div>
        </div>

        {/* Period Summary */}
        {selectedPromo && (
          <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-amber-500"></span>
              <span className="font-medium text-gray-700">Periodo Promo:</span>
              <span className="text-gray-600">
                {format(parseISO(selectedPromo.startDate), 'dd MMM', { locale: it })} - {format(parseISO(selectedPromo.endDate), 'dd MMM yyyy', { locale: it })}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-blue-500"></span>
              <span className="font-medium text-gray-700">Periodo Confronto:</span>
              <span className="text-gray-600">
                {compStartDate && compEndDate 
                  ? `${format(parseISO(compStartDate), 'dd MMM', { locale: it })} - ${format(parseISO(compEndDate), 'dd MMM yyyy', { locale: it })}`
                  : 'Non selezionato'
                }
              </span>
            </div>
          </div>
        )}
      </Card>

      {/* Error State */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Empty State */}
      {!selectedPromo && (
        <Card className="text-center py-12">
          <Gift size={48} className="mx-auto text-gray-300 mb-4" />
          <Title className="text-gray-500 mb-2">Seleziona una promozione</Title>
          <Text>Scegli una promozione dal menu sopra per visualizzare le metriche di performance</Text>
        </Card>
      )}

      {/* KPI Widgets */}
      {selectedPromo && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <KPIWidget
            title="SWI Totale"
            value={kpis.swi?.value}
            comparisonValue={kpis.swi?.comparison}
            change={kpis.swi?.change}
            loading={loading}
            decorationColor="blue"
          />
          <KPIWidget
            title="CR Commodity"
            value={kpis.crCommodity?.value}
            comparisonValue={kpis.crCommodity?.comparison}
            change={kpis.crCommodity?.change}
            unit="%"
            loading={loading}
            decorationColor="emerald"
          />
          <KPIWidget
            title="CR Luce e Gas"
            value={kpis.crLucegas?.value}
            comparisonValue={kpis.crLucegas?.comparison}
            change={kpis.crLucegas?.change}
            unit="%"
            loading={loading}
            decorationColor="violet"
          />
        </div>
      )}

      {/* Data Info */}
      {selectedPromo && promoData && (
        <div className="mt-6 text-center text-sm text-gray-400">
          Dati periodo promo: {promoData.meta?.count || 0} giorni analizzati
          {comparisonData && ` | Confronto: ${comparisonData.meta?.count || 0} giorni`}
        </div>
      )}
    </main>
  );
}

// Export memoized component
export const PromoDashboard = memo(PromoDashboardComponent);

PromoDashboard.displayName = 'PromoDashboard';

export default PromoDashboard;

