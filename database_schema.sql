-- ============================================================================
-- Proxy Scraper Database Schema for Supabase
-- ============================================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Main Proxies Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS proxies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ip INET NOT NULL,
    port INTEGER NOT NULL CHECK (port > 0 AND port <= 65535),
    type VARCHAR(10) NOT NULL CHECK (type IN ('http', 'https', 'socks4', 'socks5')),
    country VARCHAR(3), -- ISO 3166-1 alpha-3 country code
    country_name VARCHAR(100),
    city VARCHAR(100),
    anonymity_level VARCHAR(20) CHECK (anonymity_level IN ('transparent', 'anonymous', 'elite')),
    status VARCHAR(20) DEFAULT 'untested' CHECK (status IN ('active', 'inactive', 'testing', 'untested', 'failed')),
    response_time_ms INTEGER, -- Response time in milliseconds
    uptime_percentage DECIMAL(5,2) DEFAULT 0.00, -- Uptime percentage (0.00-100.00)
    last_checked TIMESTAMPTZ,
    last_working TIMESTAMPTZ,
    source_url TEXT, -- URL where this proxy was scraped from
    source_name VARCHAR(100), -- Name of the source website
    is_working BOOLEAN DEFAULT NULL,
    
    -- HTTP/HTTPS connectivity tracking
    supports_http BOOLEAN DEFAULT NULL, -- Can proxy handle HTTP requests
    supports_https BOOLEAN DEFAULT NULL, -- Can proxy handle HTTPS requests
    http_response_time_ms INTEGER, -- HTTP-specific response time
    https_response_time_ms INTEGER, -- HTTPS-specific response time
    last_http_check TIMESTAMPTZ, -- Last time HTTP was tested
    last_https_check TIMESTAMPTZ, -- Last time HTTPS was tested
    last_http_working TIMESTAMPTZ, -- Last time HTTP worked
    last_https_working TIMESTAMPTZ, -- Last time HTTPS worked
    
    failure_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    http_failure_count INTEGER DEFAULT 0,
    http_success_count INTEGER DEFAULT 0,
    https_failure_count INTEGER DEFAULT 0,
    https_success_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint to prevent duplicate proxies
    UNIQUE(ip, port, type)
);

-- ============================================================================
-- Enhanced Proxy Sources Table (Dynamic AI-Generated Configurations)
-- ============================================================================

DROP TABLE IF EXISTS ai_config_generations CASCADE;
DROP TABLE IF EXISTS proxy_sources CASCADE;

CREATE TABLE IF NOT EXISTS proxy_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Scraping configuration
    method VARCHAR(20) DEFAULT 'selenium' CHECK (method IN ('selenium', 'api', 'requests')),
    table_selector TEXT, -- CSS selector for proxy table
    ip_column INTEGER DEFAULT 0, -- Column index for IP address
    port_column INTEGER DEFAULT 1, -- Column index for port
    country_column INTEGER, -- Column index for country
    anonymity_column INTEGER, -- Column index for anonymity level
    
    -- API specific config
    api_format VARCHAR(20) CHECK (api_format IN ('json', 'text', 'csv', 'xml')),
    api_response_path TEXT, -- JSONPath or XPath for API responses
    json_ip_field VARCHAR(50), -- JSON field name for IP address (e.g., 'ip')
    json_port_field VARCHAR(50), -- JSON field name for port (e.g., 'port')
    json_country_field VARCHAR(50), -- JSON field name for country (e.g., 'country')
    json_anonymity_field VARCHAR(50), -- JSON field name for anonymity (e.g., 'anonymityLevel')
    
    -- Pagination and timing
    has_pagination BOOLEAN DEFAULT FALSE,
pagination_selector TEXT, -- XPath or CSS selector for next page button
pagination_type VARCHAR(10) DEFAULT 'click', -- 'click' or 'url' pagination
max_pages INTEGER DEFAULT 10, -- Maximum pages to scrape (prevent infinite loops)
    request_delay_seconds INTEGER DEFAULT 2,
    
    -- AI generation metadata
    ai_generated BOOLEAN DEFAULT FALSE,
    ai_model_used VARCHAR(50), -- e.g., 'gemini-1.5-flash'
    ai_generation_date TIMESTAMPTZ,
    ai_confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    ai_prompt_used TEXT,
    
    -- Success tracking
    scrape_interval_minutes INTEGER DEFAULT 60,
    last_scraped TIMESTAMPTZ,
    last_successful_scrape TIMESTAMPTZ,
    total_proxies_found INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0.00,
    consecutive_failures INTEGER DEFAULT 0,
    max_failures_before_ai_refresh INTEGER DEFAULT 3,
    
    -- Validation rules
    expected_min_proxies INTEGER DEFAULT 10, -- Minimum proxies expected per scrape
    selector_validation_rules JSONB, -- Store complex validation rules
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- AI Configuration Generation Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS ai_config_generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES proxy_sources(id) ON DELETE CASCADE,
    trigger_reason VARCHAR(100), -- 'no_results', 'consecutive_failures', 'manual_request'
    
    -- AI Request details
    ai_model VARCHAR(50) NOT NULL,
    prompt_used TEXT NOT NULL,
    website_analysis TEXT, -- What the AI observed about the site
    
    -- Generated configuration
    generated_config JSONB NOT NULL,
    confidence_score DECIMAL(3,2),
    
    -- Application results
    applied BOOLEAN DEFAULT FALSE,
    application_date TIMESTAMPTZ,
    test_results JSONB, -- Results of testing the generated config
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Proxy Check History Table (Track validation attempts)
-- ============================================================================

CREATE TABLE IF NOT EXISTS proxy_check_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proxy_id UUID NOT NULL REFERENCES proxies(id) ON DELETE CASCADE,
    check_time TIMESTAMPTZ DEFAULT NOW(),
    is_working BOOLEAN NOT NULL,
    response_time_ms INTEGER,
    error_message TEXT,
    check_method VARCHAR(50), -- 'selenium', 'requests', 'curl', etc.
    target_url TEXT, -- URL used to test the proxy
    
    -- HTTP/HTTPS specific tracking
    protocol_tested VARCHAR(10) CHECK (protocol_tested IN ('http', 'https', 'both')), -- Which protocol was tested
    http_working BOOLEAN, -- HTTP connectivity result
    https_working BOOLEAN, -- HTTPS connectivity result
    http_response_time_ms INTEGER, -- HTTP response time
    https_response_time_ms INTEGER, -- HTTPS response time
    http_error_message TEXT, -- HTTP-specific error
    https_error_message TEXT, -- HTTPS-specific error
    worker_id VARCHAR(100), -- ID of the worker that performed the test
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Scraping Jobs Table (Track scraping operations)
-- ============================================================================

CREATE TABLE IF NOT EXISTS scraping_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES proxy_sources(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    proxies_found INTEGER DEFAULT 0,
    proxies_added INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Primary indexes for frequent queries
CREATE INDEX IF NOT EXISTS idx_proxies_status ON proxies(status);
CREATE INDEX IF NOT EXISTS idx_proxies_type ON proxies(type);
CREATE INDEX IF NOT EXISTS idx_proxies_country ON proxies(country);
CREATE INDEX IF NOT EXISTS idx_proxies_last_checked ON proxies(last_checked);
CREATE INDEX IF NOT EXISTS idx_proxies_is_working ON proxies(is_working);
CREATE INDEX IF NOT EXISTS idx_proxies_created_at ON proxies(created_at);

-- HTTP/HTTPS connectivity indexes
CREATE INDEX IF NOT EXISTS idx_proxies_supports_http ON proxies(supports_http);
CREATE INDEX IF NOT EXISTS idx_proxies_supports_https ON proxies(supports_https);
CREATE INDEX IF NOT EXISTS idx_proxies_last_http_check ON proxies(last_http_check);
CREATE INDEX IF NOT EXISTS idx_proxies_last_https_check ON proxies(last_https_check);
CREATE INDEX IF NOT EXISTS idx_proxies_http_response_time ON proxies(http_response_time_ms);
CREATE INDEX IF NOT EXISTS idx_proxies_https_response_time ON proxies(https_response_time_ms);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_proxies_status_type ON proxies(status, type);
CREATE INDEX IF NOT EXISTS idx_proxies_working_response_time ON proxies(is_working, response_time_ms);
CREATE INDEX IF NOT EXISTS idx_proxies_http_https_support ON proxies(supports_http, supports_https);
CREATE INDEX IF NOT EXISTS idx_proxies_https_working_time ON proxies(supports_https, https_response_time_ms);

-- Check history indexes
CREATE INDEX IF NOT EXISTS idx_proxy_check_history_proxy_id ON proxy_check_history(proxy_id);
CREATE INDEX IF NOT EXISTS idx_proxy_check_history_check_time ON proxy_check_history(check_time);
CREATE INDEX IF NOT EXISTS idx_proxy_check_history_protocol ON proxy_check_history(protocol_tested);
CREATE INDEX IF NOT EXISTS idx_proxy_check_history_http_working ON proxy_check_history(http_working);
CREATE INDEX IF NOT EXISTS idx_proxy_check_history_https_working ON proxy_check_history(https_working);
CREATE INDEX IF NOT EXISTS idx_proxy_check_history_worker_id ON proxy_check_history(worker_id);

-- ============================================================================
-- Enhanced Indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_proxy_sources_active ON proxy_sources(is_active);
CREATE INDEX IF NOT EXISTS idx_proxy_sources_method ON proxy_sources(method);
CREATE INDEX IF NOT EXISTS idx_proxy_sources_last_scraped ON proxy_sources(last_scraped);
CREATE INDEX IF NOT EXISTS idx_proxy_sources_success_rate ON proxy_sources(success_rate);
CREATE INDEX IF NOT EXISTS idx_proxy_sources_failures ON proxy_sources(consecutive_failures);

CREATE INDEX IF NOT EXISTS idx_ai_generations_source ON ai_config_generations(source_id);
CREATE INDEX IF NOT EXISTS idx_ai_generations_applied ON ai_config_generations(applied);

-- ============================================================================
-- Functions and Triggers
-- ============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to automatically update updated_at
CREATE TRIGGER update_proxies_updated_at 
    BEFORE UPDATE ON proxies 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_proxy_sources_updated_at 
    BEFORE UPDATE ON proxy_sources 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to calculate uptime percentage
CREATE OR REPLACE FUNCTION calculate_uptime_percentage(proxy_uuid UUID)
RETURNS DECIMAL AS $$
DECLARE
    total_checks INTEGER;
    working_checks INTEGER;
    uptime_pct DECIMAL;
BEGIN
    SELECT COUNT(*) INTO total_checks
    FROM proxy_check_history
    WHERE proxy_id = proxy_uuid;
    
    IF total_checks = 0 THEN
        RETURN 0.00;
    END IF;
    
    SELECT COUNT(*) INTO working_checks
    FROM proxy_check_history
    WHERE proxy_id = proxy_uuid AND is_working = TRUE;
    
    uptime_pct := (working_checks::DECIMAL / total_checks::DECIMAL) * 100;
    
    RETURN ROUND(uptime_pct, 2);
END;
$$ LANGUAGE 'plpgsql';

-- Function to calculate HTTP-specific uptime percentage
CREATE OR REPLACE FUNCTION calculate_http_uptime_percentage(proxy_uuid UUID)
RETURNS DECIMAL AS $$
DECLARE
    total_checks INTEGER;
    working_checks INTEGER;
    uptime_pct DECIMAL;
BEGIN
    SELECT COUNT(*) INTO total_checks
    FROM proxy_check_history
    WHERE proxy_id = proxy_uuid AND (protocol_tested = 'http' OR protocol_tested = 'both');
    
    IF total_checks = 0 THEN
        RETURN 0.00;
    END IF;
    
    SELECT COUNT(*) INTO working_checks
    FROM proxy_check_history
    WHERE proxy_id = proxy_uuid 
      AND (protocol_tested = 'http' OR protocol_tested = 'both')
      AND http_working = TRUE;
    
    uptime_pct := (working_checks::DECIMAL / total_checks::DECIMAL) * 100;
    
    RETURN ROUND(uptime_pct, 2);
END;
$$ LANGUAGE 'plpgsql';

-- Function to calculate HTTPS-specific uptime percentage
CREATE OR REPLACE FUNCTION calculate_https_uptime_percentage(proxy_uuid UUID)
RETURNS DECIMAL AS $$
DECLARE
    total_checks INTEGER;
    working_checks INTEGER;
    uptime_pct DECIMAL;
BEGIN
    SELECT COUNT(*) INTO total_checks
    FROM proxy_check_history
    WHERE proxy_id = proxy_uuid AND (protocol_tested = 'https' OR protocol_tested = 'both');
    
    IF total_checks = 0 THEN
        RETURN 0.00;
    END IF;
    
    SELECT COUNT(*) INTO working_checks
    FROM proxy_check_history
    WHERE proxy_id = proxy_uuid 
      AND (protocol_tested = 'https' OR protocol_tested = 'both')
      AND https_working = TRUE;
    
    uptime_pct := (working_checks::DECIMAL / total_checks::DECIMAL) * 100;
    
    RETURN ROUND(uptime_pct, 2);
END;
$$ LANGUAGE 'plpgsql';

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- View for active proxies with good performance
CREATE OR REPLACE VIEW active_proxies AS
SELECT 
    p.*,
    calculate_uptime_percentage(p.id) as calculated_uptime,
    calculate_http_uptime_percentage(p.id) as http_uptime_percentage,
    calculate_https_uptime_percentage(p.id) as https_uptime_percentage
FROM proxies p
WHERE p.status = 'active' 
  AND p.is_working = TRUE
  AND p.last_checked > NOW() - INTERVAL '24 hours'
ORDER BY p.response_time_ms ASC NULLS LAST;

-- View for proxy statistics by country
CREATE OR REPLACE VIEW proxy_stats_by_country AS
SELECT 
    country,
    country_name,
    COUNT(*) as total_proxies,
    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_proxies,
    COUNT(CASE WHEN is_working = TRUE THEN 1 END) as working_proxies,
    COUNT(CASE WHEN supports_http = TRUE THEN 1 END) as http_working_proxies,
    COUNT(CASE WHEN supports_https = TRUE THEN 1 END) as https_working_proxies,
    AVG(response_time_ms) as avg_response_time,
    AVG(http_response_time_ms) as avg_http_response_time,
    AVG(https_response_time_ms) as avg_https_response_time,
    AVG(uptime_percentage) as avg_uptime
FROM proxies
WHERE country IS NOT NULL
GROUP BY country, country_name
ORDER BY active_proxies DESC;

-- View for HTTPS-capable proxies only
CREATE OR REPLACE VIEW https_proxies AS
SELECT 
    p.*,
    calculate_uptime_percentage(p.id) as calculated_uptime,
    calculate_https_uptime_percentage(p.id) as https_uptime_percentage
FROM proxies p
WHERE p.supports_https = TRUE 
  AND p.status = 'active'
  AND p.last_https_check > NOW() - INTERVAL '24 hours'
ORDER BY p.https_response_time_ms ASC NULLS LAST;

-- View for dual-protocol proxies (both HTTP and HTTPS)
CREATE OR REPLACE VIEW dual_protocol_proxies AS
SELECT 
    p.*,
    calculate_uptime_percentage(p.id) as calculated_uptime,
    calculate_http_uptime_percentage(p.id) as http_uptime_percentage,
    calculate_https_uptime_percentage(p.id) as https_uptime_percentage
FROM proxies p
WHERE p.supports_http = TRUE 
  AND p.supports_https = TRUE
  AND p.status = 'active'
  AND p.last_checked > NOW() - INTERVAL '24 hours'
ORDER BY 
    CASE 
        WHEN p.https_response_time_ms IS NOT NULL THEN p.https_response_time_ms 
        ELSE p.http_response_time_ms 
    END ASC NULLS LAST;

-- ============================================================================
-- Functions for AI Config Management
-- ============================================================================

-- Function to check if a source needs AI refresh
CREATE OR REPLACE FUNCTION needs_ai_refresh(source_uuid UUID)
RETURNS BOOLEAN AS $$
DECLARE
    source_record proxy_sources%ROWTYPE;
BEGIN
    SELECT * INTO source_record FROM proxy_sources WHERE id = source_uuid;
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Check if consecutive failures exceed threshold
    IF source_record.consecutive_failures >= source_record.max_failures_before_ai_refresh THEN
        RETURN TRUE;
    END IF;
    
    -- Check if last scrape had no results
    IF source_record.last_scraped IS NOT NULL 
       AND (source_record.last_successful_scrape IS NULL 
       OR source_record.last_successful_scrape < source_record.last_scraped - INTERVAL '24 hours') THEN
        RETURN TRUE;
    END IF;
    
    RETURN FALSE;
END;
$$ LANGUAGE 'plpgsql';

-- Function to mark AI refresh as needed
CREATE OR REPLACE FUNCTION mark_source_for_ai_refresh(source_uuid UUID, reason TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE proxy_sources 
    SET consecutive_failures = consecutive_failures + 1,
        updated_at = NOW()
    WHERE id = source_uuid;
    
    -- Log the need for refresh (we'll handle the actual AI call in Python)
    INSERT INTO ai_config_generations (source_id, trigger_reason, ai_model, prompt_used, generated_config)
    VALUES (source_uuid, reason, 'pending', 'pending', '{"status": "pending"}'::jsonb);
END;
$$ LANGUAGE 'plpgsql';

-- ============================================================================
-- Updated Initial Data with Enhanced Configurations
-- ============================================================================

-- Clear existing data
DELETE FROM proxy_sources;

-- Insert enhanced source configurations
INSERT INTO proxy_sources (
    name, url, method, table_selector, ip_column, port_column, country_column, anonymity_column,
    expected_min_proxies, request_delay_seconds
) VALUES
('free-proxy-list', 'https://free-proxy-list.net/', 'selenium', '.table-striped', 0, 1, 2, 4, 50, 3),
('ssl-proxies', 'https://www.sslproxies.org/', 'selenium', '.table-striped', 0, 1, 2, 4, 30, 3),
('us-proxy', 'https://www.us-proxy.org/', 'selenium', '.table-striped', 0, 1, 2, 4, 20, 3),
('socks-proxy', 'https://www.socks-proxy.net/', 'selenium', '.table-striped', 0, 1, 2, 4, 20, 4),
('proxy-list-download', 'https://www.proxy-list.download/api/v1/get?type=http', 'api', NULL, 0, 1, NULL, NULL, 100, 1)
ON CONFLICT (name) DO UPDATE SET
    url = EXCLUDED.url,
    method = EXCLUDED.method,
    table_selector = EXCLUDED.table_selector,
    ip_column = EXCLUDED.ip_column,
    port_column = EXCLUDED.port_column,
    country_column = EXCLUDED.country_column,
    anonymity_column = EXCLUDED.anonymity_column,
    expected_min_proxies = EXCLUDED.expected_min_proxies,
    request_delay_seconds = EXCLUDED.request_delay_seconds,
    updated_at = NOW();

-- ============================================================================
-- Row Level Security (RLS) - Optional
-- ============================================================================

-- Enable RLS if you want to restrict access
-- ALTER TABLE proxies ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE proxy_sources ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE proxy_check_history ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scraping_jobs ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE proxies IS 'Main table storing proxy server information';
COMMENT ON TABLE proxy_sources IS 'Table tracking websites where proxies are scraped from';
COMMENT ON TABLE proxy_check_history IS 'Historical log of proxy validation attempts';
COMMENT ON TABLE scraping_jobs IS 'Log of scraping operations and their results';

COMMENT ON COLUMN proxies.anonymity_level IS 'Level of anonymity: transparent, anonymous, or elite';
COMMENT ON COLUMN proxies.uptime_percentage IS 'Percentage of successful checks over total checks';
COMMENT ON COLUMN proxies.response_time_ms IS 'Average response time in milliseconds';
COMMENT ON COLUMN proxies.supports_http IS 'Whether the proxy can handle HTTP requests';
COMMENT ON COLUMN proxies.supports_https IS 'Whether the proxy can handle HTTPS requests';
COMMENT ON COLUMN proxies.http_response_time_ms IS 'Average HTTP response time in milliseconds';
COMMENT ON COLUMN proxies.https_response_time_ms IS 'Average HTTPS response time in milliseconds';

-- ============================================================================
-- HTTPS Testing Enhancement Summary
-- ============================================================================

/*
This schema update adds comprehensive HTTP/HTTPS testing capabilities:

NEW COLUMNS IN 'proxies' TABLE:
- supports_http: Boolean indicating HTTP connectivity
- supports_https: Boolean indicating HTTPS connectivity  
- http_response_time_ms: HTTP-specific response time
- https_response_time_ms: HTTPS-specific response time
- last_http_check: Timestamp of last HTTP test
- last_https_check: Timestamp of last HTTPS test
- last_http_working: Timestamp when HTTP last worked
- last_https_working: Timestamp when HTTPS last worked
- http_failure_count/http_success_count: HTTP-specific counters
- https_failure_count/https_success_count: HTTPS-specific counters

NEW COLUMNS IN 'proxy_check_history' TABLE:
- protocol_tested: Which protocol was tested ('http', 'https', 'both')
- http_working: HTTP connectivity result
- https_working: HTTPS connectivity result
- http_response_time_ms: HTTP response time for this test
- https_response_time_ms: HTTPS response time for this test
- http_error_message: HTTP-specific error message
- https_error_message: HTTPS-specific error message
- worker_id: ID of the validation worker

NEW FUNCTIONS:
- calculate_http_uptime_percentage(): Calculate HTTP-only uptime
- calculate_https_uptime_percentage(): Calculate HTTPS-only uptime

NEW VIEWS:
- https_proxies: Only HTTPS-capable proxies
- dual_protocol_proxies: Proxies supporting both HTTP and HTTPS

USAGE EXAMPLES:

1. Find all HTTPS-capable proxies:
   SELECT * FROM https_proxies WHERE https_uptime_percentage > 80;

2. Find fastest HTTPS proxies:
   SELECT * FROM proxies WHERE supports_https = TRUE 
   ORDER BY https_response_time_ms ASC LIMIT 10;

3. Get proxy statistics by protocol support:
   SELECT 
     COUNT(CASE WHEN supports_http = TRUE THEN 1 END) as http_count,
     COUNT(CASE WHEN supports_https = TRUE THEN 1 END) as https_count,
     COUNT(CASE WHEN supports_http = TRUE AND supports_https = TRUE THEN 1 END) as dual_count
   FROM proxies WHERE status = 'active';

4. Insert validation results for both protocols:
   INSERT INTO proxy_check_history (
     proxy_id, protocol_tested, http_working, https_working,
     http_response_time_ms, https_response_time_ms
   ) VALUES (
     'proxy-uuid', 'both', TRUE, FALSE, 1500, NULL
   );

5. Update proxy with HTTPS test results:
   UPDATE proxies SET 
     supports_https = TRUE,
     https_response_time_ms = 2000,
     last_https_check = NOW(),
     last_https_working = NOW(),
     https_success_count = https_success_count + 1
   WHERE id = 'proxy-uuid';
*/ 