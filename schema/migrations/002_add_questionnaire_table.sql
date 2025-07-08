-- Add questionnaire_data table
-- This migration adds support for daily questionnaire responses

-- Create the questionnaire_data table
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

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_questionnaire_user_date ON questionnaire_data(user_id, date);
CREATE INDEX IF NOT EXISTS idx_questionnaire_date ON questionnaire_data(date);
CREATE INDEX IF NOT EXISTS idx_questionnaire_sleep_quality ON questionnaire_data(perceived_sleep_quality);
CREATE INDEX IF NOT EXISTS idx_questionnaire_fatigue ON questionnaire_data(fatigue_level);
CREATE INDEX IF NOT EXISTS idx_questionnaire_motivation ON questionnaire_data(motivation_level);
