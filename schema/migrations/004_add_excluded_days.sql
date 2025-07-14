-- This table stores days when participants are not expected to provide data
-- (e.g., Saturdays, holidays, etc.)

CREATE TABLE IF NOT EXISTS excluded_days (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    reason VARCHAR(100) DEFAULT 'No data expected',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (group_id, date)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_excluded_days_group_date ON excluded_days(group_id, date);
CREATE INDEX IF NOT EXISTS idx_excluded_days_date ON excluded_days(date);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON excluded_days TO dashboard_user;
GRANT USAGE ON SEQUENCE excluded_days_id_seq TO dashboard_user;