-- Migration: 001_baseline_schema.sql
-- Descrizione: Schema baseline - documenta struttura esistente
-- Data: 2025-12-17
-- Updated: 2025-12-18 (PostgreSQL compatible)
-- Note: Questa migration usa IF NOT EXISTS per essere idempotente
--       su database esistenti che hanno già le tabelle.
--       Sintassi PostgreSQL - SQLite locale usa create_schema() fallback.

-- ============================================================================
-- TABELLA PRINCIPALE: daily_metrics
-- ============================================================================
-- Contiene metriche giornaliere aggregate da GA4

CREATE TABLE IF NOT EXISTS daily_metrics (
    date DATE PRIMARY KEY,
    extraction_timestamp TIMESTAMP NOT NULL,

    -- Sessioni (conteggi assoluti)
    sessioni_commodity INTEGER NOT NULL,
    sessioni_lucegas INTEGER NOT NULL,

    -- Conversioni
    swi_conversioni INTEGER NOT NULL,

    -- Conversion Rates (percentuali 0-100)
    cr_commodity REAL NOT NULL,
    cr_lucegas REAL NOT NULL,
    cr_canalizzazione REAL NOT NULL,

    -- Funnel
    start_funnel INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date DESC);


-- ============================================================================
-- TABELLA: products_performance
-- ============================================================================
-- Breakdown conversioni per prodotto (fixa, trend, pernoi, sempre)

CREATE TABLE IF NOT EXISTS products_performance (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    product_name TEXT NOT NULL,
    total_conversions REAL NOT NULL,
    percentage REAL NOT NULL,
    UNIQUE(date, product_name)
);

CREATE INDEX IF NOT EXISTS idx_products_date ON products_performance(date DESC);
CREATE INDEX IF NOT EXISTS idx_products_name ON products_performance(product_name);


-- ============================================================================
-- TABELLA: sessions_by_channel
-- ============================================================================
-- Breakdown sessioni per canale marketing

CREATE TABLE IF NOT EXISTS sessions_by_channel (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    channel TEXT NOT NULL,
    commodity_sessions INTEGER NOT NULL DEFAULT 0,
    lucegas_sessions INTEGER NOT NULL DEFAULT 0,
    UNIQUE(date, channel)
);

CREATE INDEX IF NOT EXISTS idx_channel_date ON sessions_by_channel(date DESC);
CREATE INDEX IF NOT EXISTS idx_channel_name ON sessions_by_channel(channel);
