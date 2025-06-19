CREATE OR REPLACE FUNCTION get_participant_data_consistency_rank(
    p_user_id INTEGER, 
    p_start_date DATE, 
    p_end_date DATE
) 
RETURNS TABLE (
    participant_id INTEGER,
    username TEXT,
    total_possible_days INTEGER,
    data_volume_total BIGINT,
    data_volume_mb NUMERIC,
    rank INTEGER,
    total_participants INTEGER
) AS $$
DECLARE
    v_total_participants INTEGER;
BEGIN
    -- Calculate total number of participants in the group
    SELECT COUNT(*) INTO v_total_participants
    FROM users u
    JOIN user_groups ug ON u.id = ug.user_id
    WHERE ug.group_id IN (
        SELECT group_id FROM user_groups WHERE user_id = p_user_id
    )
    AND u.role = 'participant';

    RETURN QUERY
    WITH date_range AS (
        SELECT 
            p_end_date - p_start_date + 1 AS total_days
    ),
    group_participants AS (
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
            dr.total_days AS total_possible_days,
            COALESCE(SUM(hm.data_volume), 0) AS total_data_volume,
            RANK() OVER (ORDER BY COALESCE(SUM(hm.data_volume), 0) DESC) AS participant_rank
        FROM 
            group_participants gp
        CROSS JOIN
            date_range dr
        LEFT JOIN 
            health_metrics hm ON gp.id = hm.user_id 
                AND hm.date BETWEEN p_start_date AND p_end_date
        GROUP BY 
            gp.id, gp.username, dr.total_days
    )
    SELECT 
        pd.participant_id,
        pd.username::TEXT,
        pd.total_possible_days::INTEGER,
        pd.total_data_volume,
        ROUND(pd.total_data_volume / 1024.0 / 1024.0, 2) AS data_volume_mb,
        pd.participant_rank::INTEGER,
        v_total_participants
    FROM 
        participant_data pd
    WHERE 
        pd.participant_id = p_user_id;
END;
$$ LANGUAGE plpgsql;