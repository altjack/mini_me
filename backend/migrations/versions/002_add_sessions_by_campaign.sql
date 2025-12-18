-- Migration: 002_add_sessions_by_campaign.sql
-- Descrizione: Aggiunge tabella sessions_by_campaign mancante
-- Data: 2025-12-17
-- Updated: 2025-12-18 (PostgreSQL compatible)
-- Issue: La tabella era definita nel codice ma non veniva creata
--        su database esistenti (solo su nuove installazioni).
-- Note: Questa migrazione usa sintassi PostgreSQL.
--       SQLite locale già ha la tabella via create_schema().

-- ============================================================================
-- TABELLA: sessions_by_campaign (PostgreSQL)
-- ============================================================================
-- Breakdown sessioni per campagna marketing (D-2 per ritardo GA4)

CREATE TABLE IF NOT EXISTS sessions_by_campaign (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    campaign TEXT NOT NULL,
    commodity_sessions INTEGER NOT NULL DEFAULT 0,
    lucegas_sessions INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, campaign)
);

CREATE INDEX IF NOT EXISTS idx_campaign_date ON sessions_by_campaign(date DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_name ON sessions_by_campaign(campaign);
