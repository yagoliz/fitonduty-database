-- Add data_volume column to health_metrics table
ALTER TABLE health_metrics 
ADD COLUMN IF NOT EXISTS data_volume INTEGER DEFAULT 0;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_health_metrics_data_volume ON health_metrics(data_volume);