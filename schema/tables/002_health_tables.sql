-- Health data tables for FitonDuty Dashboard

-- Health Metrics Table
CREATE TABLE IF NOT EXISTS health_metrics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    resting_hr INTEGER,
    max_hr INTEGER,
    sleep_hours NUMERIC(4,2),
    hrv_rest INTEGER,
    step_count INTEGER DEFAULT 0,
    data_volume INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, date)
);

-- Heart Rate Zones Table
CREATE TABLE IF NOT EXISTS heart_rate_zones (
    id SERIAL PRIMARY KEY,
    health_metric_id INTEGER NOT NULL REFERENCES health_metrics(id) ON DELETE CASCADE UNIQUE,
    very_light_percent NUMERIC(5,2),
    light_percent NUMERIC(5,2),
    moderate_percent NUMERIC(5,2),
    intense_percent NUMERIC(5,2),
    beast_mode_percent NUMERIC(5,2),
    CHECK (
        (very_light_percent + light_percent + moderate_percent + intense_percent + 
        beast_mode_percent) BETWEEN 99.0 AND 101.0
    )
);

-- Movement Speed Table
CREATE TABLE IF NOT EXISTS movement_speeds (
    id SERIAL PRIMARY KEY,
    health_metric_id INTEGER NOT NULL REFERENCES health_metrics(id) ON DELETE CASCADE UNIQUE,
    walking_minutes INTEGER DEFAULT 0,
    walking_fast_minutes INTEGER DEFAULT 0,
    jogging_minutes INTEGER DEFAULT 0,
    running_minutes INTEGER DEFAULT 0
);

-- Anomaly Detection Table
CREATE TABLE IF NOT EXISTS anomaly_scores (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    time_slot INTEGER NOT NULL, -- Minutes from midnight (0-1439)
    score NUMERIC(7,4) NOT NULL, 
    label VARCHAR(50), -- Optional classification label
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, date, time_slot)
);

-- Questionnaire Data Table
CREATE TABLE IF NOT EXISTS questionnaire_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    perceived_sleep_quality INTEGER CHECK (perceived_sleep_quality BETWEEN 0 AND 100),
    fatigue_level INTEGER CHECK (fatigue_level BETWEEN 0 AND 100),
    motivation_level INTEGER CHECK (motivation_level BETWEEN 0 AND 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, date)
);
