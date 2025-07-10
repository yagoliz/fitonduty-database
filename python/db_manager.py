# scripts/init_db.py
"""
Database initialization script.
This script creates all required tables and seeds the database with initial data.

Usage:
    python init_db.py [--drop] [--seed] [--config CONFIG_FILE] [--db-url DB_URL]

Options:
    --drop         Drop existing tables before creating new ones
    --seed         Seed the database with sample data
    --config       Path to configuration file (default: config/db_seed.yaml)
    --db-url       Database connection URL (overrides config file and environment variables)
    --set-permissions  Set user permissions (in case setup_database.sh is not run)
    --anomaly-interval  Interval in minutes for anomaly data (default: 5)
    --skip-anomalies  Skip generating anomaly data
"""

import argparse
from datetime import datetime, timedelta
import glob
import os
from pathlib import Path
import random
import sys

from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash
import yaml

from function_manager import execute_function_files

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def parse_args():
    parser = argparse.ArgumentParser(description='Initialize database for Health Dashboard')
    parser.add_argument('--drop', action='store_true', help='Drop existing tables before creating new ones')
    parser.add_argument('--seed', action='store_true', help='Seed the database with sample data')
    parser.add_argument('--config', default='config/db_seed.yaml', help='Path to configuration file')
    parser.add_argument('--db-url', help='Database connection URL (overrides config file)')
    parser.add_argument('--set-permissions', action='store_true', help='Set user permissions (in case setup_database.sh is not run)')
    parser.add_argument('--anomaly-interval', type=int, default=5, help='Interval in minutes for anomaly data (default: 5)')
    parser.add_argument('--skip-anomalies', action='store_true', help='Skip generating anomaly data')
    return parser.parse_args()

def load_config(config_path):
    """Load configuration from YAML file"""
    try:
        if not os.path.exists(config_path):
            print(f"Configuration file not found: {config_path}")
            return None
            
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            
        # Validate configuration structure
        if not config:
            print("Configuration file is empty")
            return None
            
        # Check for required sections for seeding
        if 'admins' not in config or 'groups' not in config or 'participants' not in config:
            print("Warning: Missing one or more required sections (admins, groups, participants) for seeding")
            # We don't return None here as the database section might still be valid
            
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return None

def create_db_engine(args, config):
    """Create database engine from args and config"""
    # Priority order:
    # 1. Command line argument (--db-url)
    # 2. Configuration file (database section)
    # 3. Environment variable (DATABASE_URL)
    # 4. Default connection string
    
    # Option 1: Command line
    if args.db_url:
        db_url = args.db_url
        print(f"Using database URL from command line: {db_url}")
        return create_engine(db_url)
    
    # Option 2: Configuration file
    if config and 'database' in config:
        db_config = config['database']
        
        # Check if complete URL is provided
        if 'url' in db_config:
            db_url = db_config['url']
            print(f"Using database URL from config file: {db_url}")
            return create_engine(db_url)
            
        # Build connection string from individual components
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', 5432)
        name = db_config.get('name', 'health_dashboard')
        user = db_config.get('user', 'username')
        password = db_config.get('password', 'password')
        
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{name}"
        print(f"Using database connection details from config file: {db_url}")
        return create_engine(db_url)
    
    # Option 3: Environment variable
    if 'DASHBOARD_ADMIN_DB_URL' in os.environ:
        db_url = os.environ['DASHBOARD_ADMIN_DB_URL']
        print(f"Using database URL from environment variable: {db_url}")
        return create_engine(db_url)
    
    # Option 4: Default
    db_url = 'postgresql://username:password@localhost:5432/health_dashboard'
    print(f"Using default database URL: {db_url}")
    return create_engine(db_url)


def execute_schema_files(engine):
    """Execute all schema files in order"""
    
    # Get the schema directory relative to this script
    script_dir = Path(__file__).parent
    schema_dir = script_dir.parent / "schema" / "tables"
    
    if not schema_dir.exists():
        print(f"Schema directory not found: {schema_dir}")
        return False
    
    # Get all .sql files and sort them by filename (001_, 002_, etc.)
    schema_files = sorted(glob.glob(str(schema_dir / "*.sql")))
    
    if not schema_files:
        print(f"No schema files found in {schema_dir}")
        return False
    
    print(f"Found {len(schema_files)} schema files to execute")
    
    try:
        with engine.begin() as conn:
            for schema_file in schema_files:
                filename = os.path.basename(schema_file)
                print(f"Executing schema file: {filename}")
                
                with open(schema_file, 'r') as f:
                    sql_content = f.read()
                
                # Split by semicolon and execute each statement
                statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
                
                for statement in statements:
                    if statement:
                        conn.execute(text(statement))
                
                print(f"✓ Executed {filename}")
        
        print("All schema files executed successfully!")
        return True
        
    except Exception as e:
        print(f"Error executing schema files: {e}")
        return False


def create_tables(engine):
    """Create all database tables using schema files"""
    print("Creating database tables from schema files...")
    return execute_schema_files(engine)


def drop_tables(engine):
    """Drop all tables from the database"""
    print("Dropping all tables...")
    
    # Get list of tables to drop
    drop_sql = """
    DO $$ 
    DECLARE 
        r RECORD;
    BEGIN
        -- Drop all tables in the public schema
        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') 
        LOOP
            EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
        END LOOP;
        
        -- Drop all sequences in the public schema
        FOR r IN (SELECT sequencename FROM pg_sequences WHERE schemaname = 'public') 
        LOOP
            EXECUTE 'DROP SEQUENCE IF EXISTS public.' || quote_ident(r.sequencename) || ' CASCADE';
        END LOOP;
    END $$;
    """
    
    try:
        with engine.begin() as conn:
            conn.execute(text(drop_sql))
        print("All tables and sequences dropped successfully!")
        return True
    except Exception as e:
        print(f"Error dropping tables: {e}")
        return False
    

def generate_questionnaire_data(user_id, start_date, end_date):
    """Generate realistic questionnaire data for a user over a date range"""
    import random
    from datetime import timedelta
    
    questionnaire_data = []
    current_date = start_date
    
    # Create some baseline patterns for this user
    base_sleep_quality = random.uniform(60, 80)
    base_fatigue = random.uniform(30, 60)
    base_motivation = random.uniform(60, 85)
    
    # Add some personality traits that affect responses
    sleep_variability = random.uniform(10, 25)
    fatigue_variability = random.uniform(15, 30)
    motivation_variability = random.uniform(10, 20)
    
    while current_date <= end_date:
        # Skip some days randomly (not everyone fills questionnaires daily)
        if random.random() < 0.15:  # 15% chance to skip a day
            current_date += timedelta(days=1)
            continue
        
        # Generate daily variations
        day_of_week = current_date.weekday()
        
        # Weekend effect
        weekend_sleep_bonus = 0.5 if day_of_week >= 5 else 0
        weekend_motivation_penalty = -0.3 if day_of_week >= 5 else 0
        
        # Weekly cycle effect
        week_progress = day_of_week / 6.0
        weekly_fatigue_increase = week_progress * 1.5
        
        # Generate values with realistic constraints
        sleep_quality = max(0, min(100, 
            base_sleep_quality + weekend_sleep_bonus + 
            random.gauss(0, sleep_variability)
        ))
        
        fatigue_level = max(0, min(100,
            base_fatigue + weekly_fatigue_increase + 
            random.gauss(0, fatigue_variability)
        ))
        
        motivation_level = max(0, min(100,
            base_motivation + weekend_motivation_penalty + 
            random.gauss(0, motivation_variability)
        ))
        
        
        questionnaire_data.append({
            'user_id': user_id,
            'date': current_date,
            'perceived_sleep_quality': round(sleep_quality),
            'fatigue_level': round(fatigue_level),
            'motivation_level': round(motivation_level),
        })
        
        current_date += timedelta(days=1)
    
    return questionnaire_data


def insert_questionnaire_data(engine, questionnaire_data):
    """Insert questionnaire data into the database"""
    from sqlalchemy import text
    
    insert_query = text("""
        INSERT INTO questionnaire_data 
        (user_id, date, perceived_sleep_quality, fatigue_level, motivation_level)
        VALUES (:user_id, :date, :perceived_sleep_quality, :fatigue_level, :motivation_level)
        ON CONFLICT (user_id, date) DO UPDATE SET
            perceived_sleep_quality = EXCLUDED.perceived_sleep_quality,
            fatigue_level = EXCLUDED.fatigue_level,
            motivation_level = EXCLUDED.motivation_level,
            created_at = CURRENT_TIMESTAMP
    """)
    
    try:
        with engine.connect() as conn:
            for data in questionnaire_data:
                conn.execute(insert_query, data)
            conn.commit()
        print(f"✓ Inserted {len(questionnaire_data)} questionnaire records")
        return True
    except Exception as e:
        print(f"✗ Error inserting questionnaire data: {e}")
        return False


def import_mock_data(engine, user_id, start_date, end_date, overwrite=False):
    """
    Generate and import mock data for a user in the given date range
    
    Args:
        engine: SQLAlchemy engine
        user_id: User ID
        start_date: Start date (can be string or date object)
        end_date: End date (can be string or date object)
        overwrite: Whether to overwrite existing data (default: False)
    """
    # First, verify that the user exists
    try:
        check_query = text("SELECT 1 FROM users WHERE id = :user_id")
        with engine.connect() as conn:
            result = conn.execute(check_query, {"user_id": user_id})
            if not result.fetchone():
                print(f"Error: User with ID {user_id} does not exist. Cannot generate health data.")
                return False
    except Exception as e:
        print(f"Error verifying user existence: {e}")
        return False
        
    # Convert string dates to datetime objects if needed
    if isinstance(start_date, str):
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            print(f"Error: Invalid start date format: {start_date}. Expected YYYY-MM-DD.")
            return False
            
    if isinstance(end_date, str):
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            print(f"Error: Invalid end date format: {end_date}. Expected YYYY-MM-DD.")
            return False
    
    # Validate date range
    if start_date > end_date:
        print(f"Error: Start date ({start_date}) is after end date ({end_date}).")
        return False
    
    # Calculate the number of days in the range
    delta = end_date - start_date
    days = delta.days + 1
    
    print(f"Generating data for user {user_id} from {start_date} to {end_date} ({days} days)")
    
    # Create date range
    date_range = [start_date + timedelta(days=i) for i in range(days)]
    
    # Generate data specific to the user (using user_id as seed for consistency)
    random.seed(hash(str(user_id)) % 2**32)
    
    # Generate base values for this user
    resting_hr_base = random.randint(55, 70)
    max_hr_base = random.randint(140, 180)
    sleep_base = random.uniform(6.5, 8.5)
    hrv_base = random.randint(40, 80)
    step_count_base = random.randint(6000, 12000)  # Base daily steps
    
    # If not overwriting, get existing dates to skip
    skip_dates = set()
    if not overwrite:
        try:
            query = text("""
                SELECT date FROM health_metrics
                WHERE user_id = :user_id AND date BETWEEN :start_date AND :end_date
            """)
            
            with engine.connect() as conn:
                result = conn.execute(query, {"user_id": user_id, "start_date": start_date, "end_date": end_date})
                skip_dates = {row[0] for row in result}
                
            if skip_dates:
                print(f"Found {len(skip_dates)} existing entries that will be skipped")
        except Exception as e:
            print(f"Warning: Error checking existing dates: {e}")
    
    # Process each date in the range
    success_count = 0
    for date in date_range:
        # Skip if we already have data for this date and not overwriting
        if date in skip_dates:
            continue
        
        # Generate metrics for this date
        # Add some weekly variation (lower steps on weekends)
        weekday = date.weekday()
        weekend_factor = 0.8 if weekday >= 5 else 1.0
        
        metrics = {
            'resting_hr': resting_hr_base + random.randint(-5, 6),
            'max_hr': max_hr_base + random.randint(-10, 11),
            'sleep_hours': max(0, sleep_base + random.normalvariate(0, 0.7)),
            'hrv_rest': max(10, hrv_base + random.randint(-15, 16)),
            'step_count': int(step_count_base * weekend_factor + random.randint(-2000, 3000)),
        }
        
        # Generate heart rate zone percentages (5 zones instead of 7)
        zone_names = ['very_light', 'light', 'moderate', 'intense', 'beast_mode']
        zone_values = []

        # Generate realistic distributions
        base_percentages = [30.0, 25.0, 20.0, 15.0, 10.0]  # Base percentages for each zone
        for base_pct in base_percentages:
            zone_values.append(max(0, min(100, base_pct + random.normalvariate(0, 5))))

        # Normalize to sum to 100%
        zone_sum = sum(zone_values)
        if zone_sum > 0:
            zone_values = [v / zone_sum * 100 for v in zone_values]

        # Add zones to metrics
        for i, (name, value) in enumerate(zip(zone_names, zone_values)):
            metrics[f'{name}_percent'] = value

        # Generate movement speed data (realistic minutes that don't sum to 24 hours)
        total_active_minutes = random.randint(30, 180)  # 30 minutes to 3 hours of movement
        walking_pct = random.uniform(0.4, 0.7)
        walking_fast_pct = random.uniform(0.15, 0.35)
        jogging_pct = random.uniform(0.05, 0.25)
        running_pct = max(0.01, 1 - walking_pct - walking_fast_pct - jogging_pct)

        # Normalize percentages
        total_pct = walking_pct + walking_fast_pct + jogging_pct + running_pct
        walking_pct /= total_pct
        walking_fast_pct /= total_pct
        jogging_pct /= total_pct
        running_pct /= total_pct

        metrics['walking_minutes'] = int(total_active_minutes * walking_pct)
        metrics['walking_fast_minutes'] = int(total_active_minutes * walking_fast_pct)
        metrics['jogging_minutes'] = int(total_active_minutes * jogging_pct)
        metrics['running_minutes'] = int(total_active_minutes * running_pct)
        
        # Save to database
        if save_health_metrics(engine, user_id, date, metrics):
            success_count += 1
    
    print(f"Successfully generated {success_count} days of health data for user {user_id}")
    return success_count > 0


def generate_mock_anomaly_data(user_id, start_date, end_date, interval_minutes=5):
    """
    Generate mock anomaly score data for a user
    
    Args:
        user_id: User ID
        start_date: Start date
        end_date: End date
        interval_minutes: Time interval between measurements (default: 5 minutes)
        
    Returns:
        List of dictionaries with anomaly data
    """
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Calculate number of days and time slots per day
    delta = end_date - start_date
    days = delta.days + 1
    slots_per_day = 24 * 60 // interval_minutes
    
    # Create date range
    date_range = [start_date + timedelta(days=i) for i in range(days)]
    
    # Seed random number generator based on user_id for consistency
    random.seed(hash(str(user_id)) % 2**32)
    
    # Generate base parameters for this user
    # Some users will have more anomalies than others
    base_anomaly_level = random.uniform(0.1, 0.3)
    variability = random.uniform(0.05, 0.15)
    
    # Create patterns for different times of day
    morning_factor = random.uniform(0.8, 1.2)
    afternoon_factor = random.uniform(0.8, 1.2)
    evening_factor = random.uniform(0.8, 1.2)
    night_factor = random.uniform(0.8, 1.2)
    
    # Occasionally add anomaly spikes
    anomaly_days = random.sample(date_range, k=min(3, len(date_range)))
    anomaly_times = [random.randint(0, slots_per_day-1) for _ in range(len(anomaly_days))]
    
    # Generate data
    anomaly_data = []
    
    for date in date_range:
        for slot in range(0, slots_per_day):
            time_minutes = slot * interval_minutes
            hour = time_minutes // 60
            
            # Base score varies by time of day
            if 6 <= hour < 12:  # Morning
                time_factor = morning_factor
            elif 12 <= hour < 18:  # Afternoon
                time_factor = afternoon_factor
            elif 18 <= hour < 22:  # Evening
                time_factor = evening_factor
            else:  # Night
                time_factor = night_factor
                
            # Calculate base score with some noise
            base_score = base_anomaly_level * time_factor
            noise = random.normalvariate(0, variability)
            score = max(0, min(1, base_score + noise))
            
            # Add occasional anomaly spikes
            if date in anomaly_days and slot == anomaly_times[anomaly_days.index(date)]:
                score = min(1.0, score + random.uniform(0.3, 0.7))
                label = random.choice(["Activity spike", "Sleep disruption", "Stress event", None])
            else:
                label = None
            
            anomaly_data.append({
                "date": date,
                "time_slot": time_minutes,
                "score": round(score, 4),
                "label": label
            })
    
    return anomaly_data


def save_health_metrics(engine, user_id, date, metrics):
    """
    Save health metrics for a user
    
    Args:
        engine: SQLAlchemy engine
        user_id: User ID
        date: Date for the metrics
        metrics: Dictionary with health metrics data
    
    Returns:
        bool: True if successful, False otherwise
    """

    # Calculate data volume
    data_volume = calculate_data_volume(metrics)

    # Validate inputs
    if not isinstance(user_id, int) or user_id <= 0:
        print(f"Error: Invalid user ID: {user_id}")
        return False
        
    if not date:
        print("Error: Date is required")
        return False
        
    if not metrics or not isinstance(metrics, dict):
        print("Error: Metrics must be a non-empty dictionary")
        return False
    
    # First insert or update the health_metrics record
    upsert_metrics_query = text("""
        INSERT INTO health_metrics 
            (user_id, date, resting_hr, max_hr, sleep_hours, hrv_rest, step_count, data_volume)
        VALUES 
            (:user_id, :date, :resting_hr, :max_hr, :sleep_hours, :hrv_rest, :step_count, :data_volume)
        ON CONFLICT (user_id, date) 
        DO UPDATE SET
            resting_hr = :resting_hr,
            max_hr = :max_hr,
            sleep_hours = :sleep_hours,
            hrv_rest = :hrv_rest,
            step_count = :step_count,
            data_volume = :data_volume,
            created_at = CURRENT_TIMESTAMP
        RETURNING id
    """)
    
    # Then insert or update the heart rate zones
    upsert_zones_query = text("""
        INSERT INTO heart_rate_zones
            (health_metric_id, very_light_percent, light_percent, moderate_percent, 
            intense_percent, beast_mode_percent)
        VALUES
            (:health_metric_id, :very_light_percent, :light_percent, :moderate_percent,
            :intense_percent, :beast_mode_percent)
        ON CONFLICT (health_metric_id)
        DO UPDATE SET
            very_light_percent = :very_light_percent,
            light_percent = :light_percent,
            moderate_percent = :moderate_percent,
            intense_percent = :intense_percent,
            beast_mode_percent = :beast_mode_percent
    """)

    # Insert or update movement speeds
    upsert_movement_query = text("""
        INSERT INTO movement_speeds
            (health_metric_id, walking_minutes, walking_fast_minutes, 
            jogging_minutes, running_minutes)
        VALUES
            (:health_metric_id, :walking_minutes, :walking_fast_minutes,
            :jogging_minutes, :running_minutes)
        ON CONFLICT (health_metric_id)
        DO UPDATE SET
            walking_minutes = :walking_minutes,
            walking_fast_minutes = :walking_fast_minutes,
            jogging_minutes = :jogging_minutes,
            running_minutes = :running_minutes
    """)
    
    try:
        with engine.begin() as conn:  # Use transaction
            # Insert or update health metrics
            metrics_result = conn.execute(
                upsert_metrics_query,
                {
                    "user_id": user_id,
                    "date": date,
                    "resting_hr": metrics.get('resting_hr'),
                    "max_hr": metrics.get('max_hr'),
                    "sleep_hours": metrics.get('sleep_hours'),
                    "hrv_rest": metrics.get('hrv_rest'),
                    "step_count": metrics.get('step_count', 0),
                    "data_volume": data_volume,
                }
            )
            
            # Get the health metric ID
            row = metrics_result.fetchone()
            if row is None:
                print(f"Error: Failed to create health metric record for user {user_id} on {date}")
                return False
                
            health_metric_id = row[0]
            
            # Insert or update heart rate zones if provided
            if all(f'{zone}_percent' in metrics for zone in ['very_light', 'light', 'moderate', 'intense', 'beast_mode']):
                conn.execute(
                    upsert_zones_query,
                    {
                        "health_metric_id": health_metric_id,
                        "very_light_percent": metrics.get('very_light_percent', 0),
                        "light_percent": metrics.get('light_percent', 0),
                        "moderate_percent": metrics.get('moderate_percent', 0),
                        "intense_percent": metrics.get('intense_percent', 0),
                        "beast_mode_percent": metrics.get('beast_mode_percent', 0)
                    }
                )

            # Insert or update movement speeds if provided
            if all(f'{activity}_minutes' in metrics for activity in ['walking', 'walking_fast', 'jogging', 'running']):
                conn.execute(
                    upsert_movement_query,
                    {
                        "health_metric_id": health_metric_id,
                        "walking_minutes": metrics.get('walking_minutes', 0),
                        "walking_fast_minutes": metrics.get('walking_fast_minutes', 0),
                        "jogging_minutes": metrics.get('jogging_minutes', 0),
                        "running_minutes": metrics.get('running_minutes', 0)
                    }
                )
            
        return True
    except Exception as e:
        print(f"Error saving health metrics for user {user_id} on {date}: {e}")
        return False
    

def calculate_data_volume(metrics):
    """
    Calculate the data volume for a health metrics record in bytes
    
    Args:
        metrics: Dictionary with health metrics data
        
    Returns:
        int: Data volume in bytes
    """
    volume = 0
    
    # Base health metrics record (~40 bytes)
    volume += 40
    
    # Heart rate zones data (if present, ~40 bytes)
    if any(f'{zone}_percent' in metrics for zone in ['very_light', 'light', 'moderate', 'intense', 'beast_mode']):
        volume += 40
    
    # Movement speeds data (if present, ~16 bytes)
    if any(f'{activity}_minutes' in metrics for activity in ['walking', 'walking_fast', 'jogging', 'running']):
        volume += 16
    
    # Note: Anomaly scores are stored separately, so we'll estimate based on typical daily patterns
    # Assume ~288 5-minute intervals per day * 8 bytes = ~2304 bytes
    # For now, add a standard amount - could be made configurable
    volume += 2304
    
    return volume


def save_anomaly_scores(engine, user_id, anomaly_data):
    """
    Save anomaly scores to the database
    
    Args:
        engine: SQLAlchemy engine
        user_id: User ID
        anomaly_data: List of dictionaries with anomaly data
        
    Returns:
        Number of records inserted
    """
    if not anomaly_data:
        return 0
    
    # Prepare batch insert query
    query = text("""
        INSERT INTO anomaly_scores (user_id, date, time_slot, score, label)
        VALUES (:user_id, :date, :time_slot, :score, :label)
        ON CONFLICT (user_id, date, time_slot) DO UPDATE SET
        score = EXCLUDED.score,
        label = EXCLUDED.label
    """)
    
    try:
        count = 0
        with engine.begin() as conn:
            # Process in batches for better performance
            batch_size = 1000
            for i in range(0, len(anomaly_data), batch_size):
                batch = anomaly_data[i:i+batch_size]
                
                # Prepare parameters for this batch
                params = []
                for item in batch:
                    params.append({
                        "user_id": user_id,
                        "date": item["date"],
                        "time_slot": item["time_slot"],
                        "score": item["score"],
                        "label": item["label"]
                    })
                
                # Execute batch insert
                conn.execute(query, params)
                count += len(batch)
                
                print(f"Inserted batch of {len(batch)} anomaly records for user {user_id}")
        
        return count
    except Exception as e:
        print(f"Error saving anomaly scores: {e}")
        return 0
    

def seed_database(engine, config):
    """Seed the database with data from configuration file"""
    if not config:
        print("Cannot seed database: configuration is missing or invalid")
        return
        
    # Check for required sections
    if 'admins' not in config or 'groups' not in config or 'participants' not in config:
        print("Cannot seed database: missing required sections (admins, groups, participants)")
        return
        
    admin_ids = {}
    group_map = {}
    participant_ids = {}  # Store participant IDs for reference
    
    try:
        # First create all users (admins and participants)
        print("Creating admin users...")
        for admin in config['admins']:
            try:
                admin_user = {
                    "username": admin['username'],
                    "password_hash": generate_password_hash(admin['password']),
                    "role": "admin"
                }
                
                admin_query = text("""
                    INSERT INTO users (username, password_hash, role)
                    VALUES (:username, :password_hash, :role)
                    ON CONFLICT (username) DO UPDATE SET
                    password_hash = :password_hash
                    RETURNING id
                """)
                
                with engine.begin() as conn:
                    admin_result = conn.execute(admin_query, admin_user)
                    row = admin_result.fetchone()
                    if row:
                        admin_id = row[0]
                        admin_ids[admin['username']] = admin_id
                        print(f"Admin user created: {admin['username']} (ID: {admin_id})")
            except Exception as e:
                print(f"Error creating admin user {admin.get('username', 'unknown')}: {e}")
        
        if not admin_ids:
            print("Warning: No admin users were created. Group creation may fail.")
        
        # Process groups
        print("\nCreating groups...")
        for group in config['groups']:
            group_id = create_group(
                engine,
                group['name'],
                group['description'],
                group['created_by'],
                group.get('campaign_start_date')
            )

            group_map[group['name']] = group_id
        
        if not group_map:
            print("Warning: No groups were created. Participant group assignments will fail.")
        
        # Process participants
        print("\nCreating participants...")
        for participant in config['participants']:
            try:
                participant_data = {
                    "username": participant['username'],
                    "password_hash": generate_password_hash(participant['password']),
                    "role": "participant"
                }
                
                participant_query = text("""
                    INSERT INTO users (username, password_hash, role)
                    VALUES (:username, :password_hash, :role)
                    ON CONFLICT (username) DO UPDATE SET
                    password_hash = :password_hash
                    RETURNING id
                """)
                
                with engine.begin() as conn:
                    participant_result = conn.execute(participant_query, participant_data)
                    row = participant_result.fetchone()
                    if row:
                        participant_id = row[0]
                        participant_ids[participant['username']] = participant_id
                        print(f"Participant created: {participant['username']} (ID: {participant_id})")
                        
                        # Assign participant to group(s)
                        group_names = participant.get('groups', [])
                        if isinstance(group_names, str):
                            group_names = [group_names]  # Convert single string to list
                            
                        for group_name in group_names:
                            group_id = group_map.get(group_name)
                            if group_id:
                                group_assign_query = text("""
                                    INSERT INTO user_groups (user_id, group_id)
                                    VALUES (:user_id, :group_id)
                                    ON CONFLICT (user_id, group_id) DO NOTHING
                                """)
                                
                                conn.execute(group_assign_query, {"user_id": participant_id, "group_id": group_id})
                                print(f"  - Assigned to group: {group_name}")
                            else:
                                print(f"  - Warning: Group '{group_name}' not found, skipping assignment")
            except Exception as e:
                print(f"Error creating participant {participant.get('username', 'unknown')}: {e}")
        
        # Generate health data separately to ensure all participants are created first
        print("\nGenerating health data...")
        for participant in config['participants']:
            try:
                participant_id = participant_ids.get(participant['username'])
                
                if participant_id and participant.get('generate_data', True):
                    data_days = participant.get('data_days', 60)
                    today = datetime.now().date()
                    start_date = today - timedelta(days=data_days)
                    
                    print(f"Generating {data_days} days of health data for {participant['username']}...")
                    success = import_mock_data(engine, participant_id, start_date, today)
                    if not success:
                        print(f"  - Failed to generate health data for {participant['username']}")

                    # Generate questionnaire data
                    print(f"Generating questionnaire data for {participant['username']}...")
                    questionnaire_data = generate_questionnaire_data(
                        participant_id, 
                        start_date, 
                        today
                    )

                    if questionnaire_data:
                        if insert_questionnaire_data(engine, questionnaire_data):
                            print(f"  - Inserted {len(questionnaire_data)} questionnaire records")
                        else:
                            print(f"  - Failed to insert questionnaire data for {participant['username']}")
                        
                    # Generate anomaly scores
                    print(f"Generating anomaly scores for {participant['username']}...")
                    anomaly_data = generate_mock_anomaly_data(
                        participant_id, 
                        start_date, 
                        today,
                        interval_minutes=5  # Generate data every 5 minutes
                    )
                    if anomaly_data:
                        count = save_anomaly_scores(engine, participant_id, anomaly_data)
                        print(f"  - Generated {count} anomaly records")
                    else:
                        print(f"  - Failed to generate anomaly data for {participant['username']}")
            except Exception as e:
                print(f"Error generating data for {participant.get('username', 'unknown')}: {e}")
                
        print("\nDatabase seeded successfully!")
    except Exception as e:
        print(f"Error seeding database: {e}")
        return False
    
    return True


def create_group(engine, group_name, description, created_by_username, campaign_start_date=None):
    """Create a new group with optional campaign start date"""
    from sqlalchemy import text
    
    # Get the creator's user ID
    creator_query = text("SELECT id FROM users WHERE username = :username")
    
    try:
        with engine.connect() as conn:
            creator_result = conn.execute(creator_query, {"username": created_by_username})
            creator_row = creator_result.fetchone()
            
            if not creator_row:
                print(f"✗ Creator user '{created_by_username}' not found")
                return None
            
            creator_id = creator_row[0]
            
            # Insert the group with campaign start date
            if campaign_start_date:
                insert_query = text("""
                    INSERT INTO groups (group_name, description, created_by, campaign_start_date)
                    VALUES (:group_name, :description, :created_by, :campaign_start_date)
                    RETURNING id
                """)
                params = {
                    "group_name": group_name,
                    "description": description,
                    "created_by": creator_id,
                    "campaign_start_date": campaign_start_date
                }
            else:
                insert_query = text("""
                    INSERT INTO groups (group_name, description, created_by)
                    VALUES (:group_name, :description, :created_by)
                    RETURNING id
                """)
                params = {
                    "group_name": group_name,
                    "description": description,
                    "created_by": creator_id
                }
            
            result = conn.execute(insert_query, params)
            group_id = result.fetchone()[0]
            conn.commit()
            
            campaign_info = f" (campaign starts: {campaign_start_date})" if campaign_start_date else ""
            print(f"✓ Created group: {group_name}{campaign_info}")
            return group_id
            
    except Exception as e:
        print(f"✗ Error creating group {group_name}: {e}")
        return None


def main():
    args = parse_args()
    
    try:
        # Load configuration
        config = None
        if args.config:
            config = load_config(args.config)
        
        # Create database engine
        engine = create_db_engine(args, config)
        
        # Test database connection
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database connection successful")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            sys.exit(1)
        
        # Drop tables if requested
        if args.drop:
            try:
                if not drop_tables(engine):
                    sys.exit(1)
            except Exception as e:
                print(f"Error dropping tables: {e}")
                sys.exit(1)
        
        # Create tables using schema files
        try:
            if not create_tables(engine):
                sys.exit(1)
        except Exception as e:
            print(f"Error creating tables: {e}")
            sys.exit(1)

        # Execute function files
        try:
            if not execute_function_files(engine):
                sys.exit(1)
        except Exception as e:
            print(f"Error executing functions: {e}")
            sys.exit(1)

        # Set permissions if requested
        if args.set_permissions:
            print("Note: Permissions are now handled by schema files")
        
        # Seed database if requested
        if args.seed:
            if not config:
                print("Error: Cannot seed database without valid configuration.")
                sys.exit(1)
                
            try:
                seed_database(engine, config)
            except Exception as e:
                print(f"Error seeding database: {e}")
                sys.exit(1)
            
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()