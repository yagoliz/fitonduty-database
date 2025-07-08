-- Performance indexes for FitonDuty Dashboard

-- Health metrics indexes
CREATE INDEX IF NOT EXISTS idx_health_metrics_user_date ON health_metrics(user_id, date);
CREATE INDEX IF NOT EXISTS idx_health_metrics_date ON health_metrics(date);

-- Data volume index
CREATE INDEX IF NOT EXISTS idx_health_metrics_data_volume ON health_metrics(data_volume);

-- User groups indexes
CREATE INDEX IF NOT EXISTS idx_user_groups_group ON user_groups(group_id);
CREATE INDEX IF NOT EXISTS idx_user_groups_user ON user_groups(user_id);

-- Sessions indexes
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- Anomaly scores indexes
CREATE INDEX IF NOT EXISTS idx_anomaly_user_date ON anomaly_scores(user_id, date);
CREATE INDEX IF NOT EXISTS idx_anomaly_date_range ON anomaly_scores(date);
CREATE INDEX IF NOT EXISTS idx_anomaly_user_time ON anomaly_scores(user_id, time_slot);

-- User indexes
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

-- Groups indexes
CREATE INDEX IF NOT EXISTS idx_groups_creator ON groups(created_by);

-- Questionnaire data indexes
CREATE INDEX IF NOT EXISTS idx_questionnaire_user_date ON questionnaire_data(user_id, date);
CREATE INDEX IF NOT EXISTS idx_questionnaire_date ON questionnaire_data(date);
CREATE INDEX IF NOT EXISTS idx_questionnaire_sleep_quality ON questionnaire_data(perceived_sleep_quality);
CREATE INDEX IF NOT EXISTS idx_questionnaire_fatigue ON questionnaire_data(fatigue_level);
CREATE INDEX IF NOT EXISTS idx_questionnaire_motivation ON questionnaire_data(motivation_level);