-- sql/functions/group_participants_ranking.sql
CREATE OR REPLACE FUNCTION get_group_participants_ranking(
    p_user_id INTEGER, 
    p_start_date DATE, 
    p_end_date DATE
) 
RETURNS TABLE (
    participant_id INTEGER,
    username TEXT,
    days_with_data INTEGER,
    consistency_percentage NUMERIC,
    rank INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH date_range AS (
        SELECT p_end_date - p_start_date + 1 AS total_days
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
            COUNT(hm.date) AS days_with_data,
            (COUNT(hm.date)::NUMERIC / dr.total_days::NUMERIC) * 100 AS consistency_percentage,
            RANK() OVER (ORDER BY COUNT(hm.date) DESC) AS participant_rank
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
        pd.days_with_data::INTEGER,
        pd.consistency_percentage,
        pd.participant_rank::INTEGER
    FROM 
        participant_data pd
    ORDER BY 
        pd.participant_rank;
END;
$$ LANGUAGE plpgsql;