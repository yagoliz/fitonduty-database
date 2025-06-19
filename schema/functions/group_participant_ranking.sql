CREATE OR REPLACE FUNCTION get_group_participants_ranking(
    p_user_id INTEGER, 
    p_start_date DATE, 
    p_end_date DATE
) 
RETURNS TABLE (
    participant_id INTEGER,
    username TEXT,
    data_volume_total BIGINT,
    data_volume_mb NUMERIC,
    rank INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH group_participants AS (
        SELECT 
            u.id, 
            u.username
        FROM 
            users u
        JOIN 
            user_groups ug ON u.id = ug.user_id
        WHERE 
            ug.group_id IN (
                SELECT group_id FROM user_groups WHERE user_id = p_user_id
            )
            AND u.role = 'participant'
    ),
    participant_data AS (
        SELECT 
            gp.id AS participant_id, 
            gp.username,
            COALESCE(SUM(hm.data_volume), 0) AS total_data_volume,
            RANK() OVER (ORDER BY COALESCE(SUM(hm.data_volume), 0) DESC) AS participant_rank
        FROM 
            group_participants gp
        LEFT JOIN 
            health_metrics hm ON gp.id = hm.user_id 
                AND hm.date BETWEEN p_start_date AND p_end_date
        GROUP BY 
            gp.id, gp.username
    )
    SELECT 
        pd.participant_id,
        pd.username::TEXT,
        pd.total_data_volume,
        ROUND(pd.total_data_volume / 1024.0 / 1024.0, 2) AS data_volume_mb,
        pd.participant_rank::INTEGER
    FROM 
        participant_data pd
    ORDER BY 
        pd.participant_rank;
END;
$$ LANGUAGE plpgsql;