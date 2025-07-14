-- Function to get questionnaire data (simpler syntax)
CREATE OR REPLACE FUNCTION get_participant_questionnaire_data(
    p_user_id INTEGER,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS SETOF questionnaire_data
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM questionnaire_data qd
    WHERE qd.user_id = p_user_id
    AND qd.date BETWEEN p_start_date AND p_end_date
    ORDER BY qd.date;
END;
$$;

-- Completion rate function
CREATE OR REPLACE FUNCTION get_questionnaire_completion_rate(
    p_user_id INTEGER,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    participant_id INTEGER,
    total_possible_days INTEGER,
    questionnaire_days INTEGER,
    completion_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p_user_id as participant_id,
        (p_end_date - p_start_date + 1) as total_possible_days,
        COALESCE(COUNT(qd.date), 0)::INTEGER as questionnaire_days,
        CASE
            WHEN (p_end_date - p_start_date + 1) > 0 THEN
                ROUND((COALESCE(COUNT(qd.date), 0)::NUMERIC / (p_end_date - p_start_date + 1)) * 100, 2)
            ELSE 0
        END as completion_rate
    FROM (
        SELECT p_user_id as uid, p_start_date as start_d, p_end_date as end_d
    ) params
    LEFT JOIN questionnaire_data qd ON qd.user_id = params.uid
        AND qd.date BETWEEN params.start_d AND params.end_d
    GROUP BY params.uid, params.start_d, params.end_d;
END;
$$ LANGUAGE plpgsql;

-- Function to get questionnaire completion ranking for a participant (updated with campaign start date)
CREATE OR REPLACE FUNCTION get_participant_questionnaire_rank(
    p_user_id INTEGER,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    participant_id INTEGER,
    username TEXT,
    total_possible_days INTEGER,
    questionnaire_days INTEGER,
    completion_rate NUMERIC,
    rank INTEGER,
    total_participants INTEGER,
    campaign_start_date DATE
) AS $$
DECLARE
    v_total_participants INTEGER;
    v_campaign_start_date DATE;
    v_effective_start_date DATE;
BEGIN
    -- Get campaign start date for the user's group
    SELECT g.campaign_start_date INTO v_campaign_start_date
    FROM groups g
    JOIN user_groups ug ON g.id = ug.group_id
    WHERE ug.user_id = p_user_id
    LIMIT 1;
    
    -- Use campaign start date if available, otherwise fall back to provided start_date
    v_effective_start_date := COALESCE(v_campaign_start_date, p_start_date);

    -- Calculate total number of participants in the group
    SELECT COUNT(*) INTO v_total_participants
    FROM users u
    JOIN user_groups ug ON u.id = ug.user_id
    WHERE ug.group_id IN (
        SELECT group_id FROM user_groups WHERE user_id = p_user_id
    )
    AND u.role = 'participant';

    RETURN QUERY
    SELECT 
        p_user_id,
        u.username::TEXT,
        (p_end_date - v_effective_start_date + 1)::INTEGER as total_possible_days,
        COUNT(qd.date)::INTEGER as questionnaire_days,
        CASE 
            WHEN (p_end_date - v_effective_start_date + 1) > 0 THEN 
                ROUND((COUNT(qd.date)::NUMERIC / (p_end_date - v_effective_start_date + 1)) * 100, 2)
            ELSE 0::NUMERIC
        END as completion_rate,
        (
            SELECT COUNT(*) + 1 
            FROM (
                SELECT 
                    gp.id,
                    COUNT(qd2.date) as other_questionnaire_days
                FROM users gp
                JOIN user_groups ug2 ON gp.id = ug2.user_id
                LEFT JOIN questionnaire_data qd2 ON gp.id = qd2.user_id 
                    AND qd2.date BETWEEN v_effective_start_date AND p_end_date
                WHERE ug2.group_id IN (
                    SELECT group_id FROM user_groups WHERE user_id = p_user_id
                )
                AND gp.role = 'participant'
                AND gp.id != p_user_id
                GROUP BY gp.id
                HAVING COUNT(qd2.date) > (
                    SELECT COUNT(*) FROM questionnaire_data qd3 
                    WHERE qd3.user_id = p_user_id 
                    AND qd3.date BETWEEN v_effective_start_date AND p_end_date
                )
            ) better_participants
        )::INTEGER as rank,
        v_total_participants,
        v_campaign_start_date
    FROM users u
    JOIN user_groups ug ON u.id = ug.user_id
    LEFT JOIN questionnaire_data qd ON u.id = qd.user_id 
        AND qd.date BETWEEN v_effective_start_date AND p_end_date
    WHERE u.id = p_user_id
    GROUP BY u.id, u.username;
END;
$$ LANGUAGE plpgsql;

-- Function to get all participants' questionnaire ranking in a group (updated with campaign start date)
CREATE OR REPLACE FUNCTION get_group_questionnaire_ranking(
    p_user_id INTEGER,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    participant_id INTEGER,
    username TEXT,
    questionnaire_days INTEGER,
    completion_rate NUMERIC,
    rank INTEGER,
    campaign_start_date DATE
) AS $$
DECLARE
    v_campaign_start_date DATE;
BEGIN
    -- Get campaign start date for the user's group
    SELECT g.campaign_start_date INTO v_campaign_start_date
    FROM groups g
    JOIN user_groups ug ON g.id = ug.group_id
    WHERE ug.user_id = p_user_id
    LIMIT 1;
    
    -- If no campaign start date is set, use the provided start_date
    IF v_campaign_start_date IS NULL THEN
        v_campaign_start_date := p_start_date;
    END IF;
    
    -- Use the later of campaign start date or provided start date
    v_campaign_start_date := GREATEST(v_campaign_start_date, p_start_date);

    RETURN QUERY
    date_range AS (
        SELECT 
            v_effective_start_date as effective_start_date,
            p_end_date as end_date,
            (p_end_date - v_effective_start_date + 1) - COALESCE(excluded_count.count, 0) AS total_days
        FROM (
            SELECT COUNT(*) as count
            FROM excluded_days ed
            JOIN user_groups ug ON ed.group_id = ug.group_id
            WHERE ug.user_id = p_user_id
            AND ed.date BETWEEN v_effective_start_date AND p_end_date
        ) excluded_count
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
    participant_questionnaire_data AS (
        SELECT 
            gp.id AS participant_id, 
            gp.username,
            COALESCE(COUNT(qd.date), 0) AS questionnaire_days,
            CASE 
                WHEN dr.total_days > 0 THEN 
                    ROUND((COALESCE(COUNT(qd.date), 0)::NUMERIC / dr.total_days) * 100, 2)
                ELSE 0
            END AS completion_rate,
            RANK() OVER (ORDER BY COALESCE(COUNT(qd.date), 0) DESC) AS participant_rank
        FROM 
            group_participants gp
        CROSS JOIN
            date_range dr
        LEFT JOIN 
            questionnaire_data qd ON gp.id = qd.user_id 
                AND qd.date BETWEEN dr.effective_start_date AND dr.end_date
        GROUP BY 
            gp.id, gp.username, dr.total_days
    )
    SELECT 
        pqd.participant_id,
        pqd.username::TEXT,
        pqd.questionnaire_days::INTEGER,
        pqd.completion_rate,
        pqd.participant_rank::INTEGER,
        v_campaign_start_date
    FROM 
        participant_questionnaire_data pqd
    ORDER BY 
        pqd.participant_rank;
END;
$$ LANGUAGE plpgsql;


-- Grant execute permissions
GRANT EXECUTE ON FUNCTION get_participant_questionnaire_data(INTEGER, DATE, DATE) TO dashboard_user;
GRANT EXECUTE ON FUNCTION get_questionnaire_completion_rate(INTEGER, DATE, DATE) TO dashboard_user;
GRANT EXECUTE ON FUNCTION get_participant_questionnaire_rank(INTEGER, DATE, DATE) TO dashboard_user;
GRANT EXECUTE ON FUNCTION get_group_questionnaire_ranking(INTEGER, DATE, DATE) TO dashboard_user;