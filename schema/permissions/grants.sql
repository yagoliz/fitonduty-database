-- Database permissions for FitonDuty Dashboard

-- Grant base permissions to dashboard_user
GRANT USAGE ON SCHEMA public TO dashboard_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dashboard_user;
GRANT SELECT, USAGE ON ALL SEQUENCES IN SCHEMA public TO dashboard_user;

-- Grant specific write permissions
GRANT INSERT, UPDATE, DELETE ON sessions TO dashboard_user;
GRANT USAGE ON SEQUENCE sessions_id_seq TO dashboard_user;

GRANT INSERT, UPDATE ON health_metrics TO dashboard_user;
GRANT USAGE ON SEQUENCE health_metrics_id_seq TO dashboard_user;

GRANT INSERT, UPDATE ON heart_rate_zones TO dashboard_user;
GRANT USAGE ON SEQUENCE heart_rate_zones_id_seq TO dashboard_user;

GRANT INSERT, UPDATE ON movement_speeds TO dashboard_user;
GRANT USAGE ON SEQUENCE movement_speeds_id_seq TO dashboard_user;

GRANT INSERT, UPDATE ON anomaly_scores TO dashboard_user;
GRANT USAGE ON SEQUENCE anomaly_scores_id_seq TO dashboard_user;

GRANT INSERT, UPDATE ON user_notes TO dashboard_user;
GRANT USAGE ON SEQUENCE user_notes_id_seq TO dashboard_user;

GRANT SELECT ON users TO dashboard_user;
GRANT UPDATE (last_login) ON users TO dashboard_user;
GRANT USAGE ON SEQUENCE users_id_seq TO dashboard_user;

-- Default privileges for future objects
ALTER DEFAULT PRIVILEGES FOR ROLE dashboard_admin IN SCHEMA public 
GRANT SELECT ON TABLES TO dashboard_user;

ALTER DEFAULT PRIVILEGES FOR ROLE dashboard_admin IN SCHEMA public 
GRANT SELECT, USAGE ON SEQUENCES TO dashboard_user;

ALTER DEFAULT PRIVILEGES FOR ROLE dashboard_admin IN SCHEMA public 
GRANT EXECUTE ON FUNCTIONS TO dashboard_user;