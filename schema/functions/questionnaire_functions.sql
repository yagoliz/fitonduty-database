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

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION get_participant_questionnaire_data(INTEGER, DATE, DATE) TO dashboard_user;
GRANT EXECUTE ON FUNCTION get_questionnaire_completion_rate(INTEGER, DATE, DATE) TO dashboard_user;