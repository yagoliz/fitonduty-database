-- Add campaign start date to groups table
ALTER TABLE groups ADD COLUMN IF NOT EXISTS campaign_start_date DATE;

-- Set default campaign start date for existing groups (adjust as needed)
UPDATE groups 
SET campaign_start_date = '2024-01-01' 
WHERE campaign_start_date IS NULL;

-- Add a comment
COMMENT ON COLUMN groups.campaign_start_date IS 'The date when the campaign/study period begins for this group';