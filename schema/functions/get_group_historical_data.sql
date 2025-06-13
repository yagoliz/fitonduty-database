CREATE OR REPLACE FUNCTION get_group_historical_data(
    p_user_id INTEGER,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    date DATE,
    participant_id INTEGER,
    participant_name VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        hm.date,
        u.id AS participant_id,
        u.username AS participant_name
    FROM 
        health_metrics hm
    JOIN 
        users u ON hm.user_id = u.id
    JOIN 
        user_groups ug ON u.id = ug.user_id
    WHERE 
        ug.group_id IN (
            SELECT group_id FROM user_groups WHERE user_id = p_user_id
        )
        AND u.role = 'participant'
        AND hm.date BETWEEN p_start_date AND p_end_date
    ORDER BY 
        hm.date, u.id;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permission to dashboard_user
GRANT EXECUTE ON FUNCTION get_group_historical_data(INTEGER, DATE, DATE) TO dashboard_user;