-- Add data_volume column to health_metrics table
ALTER TABLE health_metrics 
ADD COLUMN IF NOT EXISTS data_volume INTEGER DEFAULT 0;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_health_metrics_data_volume ON health_metrics(data_volume);

-- Update existing records with calculated data volume
UPDATE health_metrics SET data_volume = (
    40 + -- Base health metrics
    CASE WHEN EXISTS(SELECT 1 FROM heart_rate_zones WHERE health_metric_id = health_metrics.id) 
         THEN 40 ELSE 0 END + -- Heart rate zones
    CASE WHEN EXISTS(SELECT 1 FROM movement_speeds WHERE health_metric_id = health_metrics.id) 
         THEN 16 ELSE 0 END + -- Movement speeds  
    2304 -- Estimated anomaly data
) WHERE data_volume = 0;