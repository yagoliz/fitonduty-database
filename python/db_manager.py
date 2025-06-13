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
import os
import sys
import argparse
import yaml
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

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

def create_tables(engine):
    """Create all database tables"""
    # SQL statements to create tables
    sql_statements = [
        # Users Table
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'participant')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
        """,
        
        # Groups Table
        """
        CREATE TABLE IF NOT EXISTS groups (
            id SERIAL PRIMARY KEY,
            group_name VARCHAR(50) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER REFERENCES users(id)
        )
        """,
        
        # User-Group Relationship Table
        """
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, group_id)
        )
        """,
        
        # Health Metrics Table
        """
        CREATE TABLE IF NOT EXISTS health_metrics (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            resting_hr INTEGER,
            max_hr INTEGER,
            sleep_hours NUMERIC(4,2),
            hrv_rest INTEGER,
            step_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, date)
        )
        """,
        
        # Heart Rate Zones Table
        """
        CREATE TABLE IF NOT EXISTS heart_rate_zones (
            id SERIAL PRIMARY KEY,
            health_metric_id INTEGER NOT NULL REFERENCES health_metrics(id) ON DELETE CASCADE UNIQUE,
            very_light_percent NUMERIC(5,2),
            light_percent NUMERIC(5,2),
            moderate_percent NUMERIC(5,2),
            intense_percent NUMERIC(5,2),
            beast_mode_percent NUMERIC(5,2),
            CHECK (
                (very_light_percent + light_percent + moderate_percent + intense_percent + 
                beast_mode_percent) BETWEEN 99.0 AND 101.0
            )
        )
        """,

        # Movement Speed Table
        """
        CREATE TABLE IF NOT EXISTS movement_speeds (
            id SERIAL PRIMARY KEY,
            health_metric_id INTEGER NOT NULL REFERENCES health_metrics(id) ON DELETE CASCADE UNIQUE,
            walking_minutes INTEGER DEFAULT 0,
            walking_fast_minutes INTEGER DEFAULT 0,
            jogging_minutes INTEGER DEFAULT 0,
            running_minutes INTEGER DEFAULT 0
        )
        """,
        
        # Sessions Table
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_token VARCHAR(255) UNIQUE NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
        """,
        
        # User Notes Table
        """
        CREATE TABLE IF NOT EXISTS user_notes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            author_id INTEGER NOT NULL REFERENCES users(id),
            note TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # Anomaly Detection Table
        """
        CREATE TABLE IF NOT EXISTS anomaly_scores (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            time_slot INTEGER NOT NULL, -- Minutes from midnight (0-1439)
            score NUMERIC(7,4) NOT NULL, 
            label VARCHAR(50), -- Optional classification label
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, date, time_slot)
        )
        """,
        
        # Create indexes for performance
        """
        CREATE INDEX IF NOT EXISTS idx_health_metrics_user_date ON health_metrics(user_id, date)
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_user_groups_group ON user_groups(group_id)
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_anomaly_user_date ON anomaly_scores(user_id, date)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_anomaly_date_range ON anomaly_scores(date)
        """
    ]
    
    # Execute all statements
    with engine.begin() as conn:
        for statement in sql_statements:
            conn.execute(text(statement))
    
    print("Tables created successfully!")


def set_user_permissions(engine):
    """
    Grant appropriate permissions to dashboard_user role
    """
    permission_statements = [
        # Grant base permissions
        """
        GRANT USAGE ON SCHEMA public TO dashboard_user;
        """,
        """
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO dashboard_user;
        """,
        """
        GRANT SELECT, USAGE ON ALL SEQUENCES IN SCHEMA public TO dashboard_user;
        """,
        
        # Grant specific write permissions
        """
        GRANT INSERT, UPDATE, DELETE ON sessions TO dashboard_user;
        """,
        """
        GRANT USAGE ON SEQUENCE sessions_id_seq TO dashboard_user;
        """,
        """
        GRANT INSERT, UPDATE ON health_metrics TO dashboard_user;
        """,
        """
        GRANT USAGE ON SEQUENCE health_metrics_id_seq TO dashboard_user;
        """,
        """
        GRANT INSERT, UPDATE ON heart_rate_zones TO dashboard_user;
        """,
        """
        GRANT USAGE ON SEQUENCE heart_rate_zones_id_seq TO dashboard_user;
        """,
        """
        GRANT INSERT, UPDATE ON user_notes TO dashboard_user;
        """,
        """
        GRANT USAGE ON SEQUENCE user_notes_id_seq TO dashboard_user;
        """,
        """
        GRANT SELECT ON users TO dashboard_user;
        """,
        """
        GRANT UPDATE (last_login) ON users TO dashboard_user;
        """,
        """
        GRANT USAGE ON SEQUENCE users_id_seq TO dashboard_user;
        """,
        
        # Default privileges for future objects
        """
        ALTER DEFAULT PRIVILEGES FOR ROLE dashboard_admin IN SCHEMA public 
        GRANT SELECT ON TABLES TO dashboard_user;
        """,
        """
        ALTER DEFAULT PRIVILEGES FOR ROLE dashboard_admin IN SCHEMA public 
        GRANT SELECT, USAGE ON SEQUENCES TO dashboard_user;
        """,
        """
        ALTER DEFAULT PRIVILEGES FOR ROLE dashboard_admin IN SCHEMA public 
        GRANT EXECUTE ON FUNCTIONS TO dashboard_user;
        """
    ]
    
    with engine.begin() as conn:
        for statement in permission_statements:
            try:
                conn.execute(text(statement))
                print(f"Executed permission statement: {statement.strip()}")
            except Exception as e:
                print(f"Error setting permission: {e}")
                print(f"Statement: {statement}")

    print("User permissions set successfully!")


def drop_tables(engine):
    """Drop all tables from the database"""
    # List of tables to drop in correct order for foreign key constraints
    tables = [
        "user_notes",
        "sessions",
        "heart_rate_zones",
        "health_metrics",
        "user_groups",
        "groups",
        "users"
    ]
    
    drop_statements = [f"DROP TABLE IF EXISTS {table} CASCADE" for table in tables]
    
    # Execute all drop statements
    with engine.begin() as conn:
        for statement in drop_statements:
            conn.execute(text(statement))
    
    print("Tables dropped successfully!")

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
            (user_id, date, resting_hr, max_hr, sleep_hours, hrv_rest, step_count)
        VALUES 
            (:user_id, :date, :resting_hr, :max_hr, :sleep_hours, :hrv_rest, :step_count)
        ON CONFLICT (user_id, date) 
        DO UPDATE SET
            resting_hr = :resting_hr,
            max_hr = :max_hr,
            sleep_hours = :sleep_hours,
            hrv_rest = :hrv_rest,
            step_count = :step_count,
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
            try:
                # Get creator ID (default to first admin if not specified)
                creator_username = group.get('created_by', list(admin_ids.keys())[0] if admin_ids else None)
                creator_id = admin_ids.get(creator_username)
                
                group_data = {
                    "group_name": group['name'],
                    "description": group.get('description', ''),
                    "created_by": creator_id
                }
                
                group_query = text("""
                    INSERT INTO groups (group_name, description, created_by)
                    VALUES (:group_name, :description, :created_by)
                    ON CONFLICT (group_name) DO UPDATE SET
                    description = :description
                    RETURNING id
                """)
                
                with engine.begin() as conn:
                    group_result = conn.execute(group_query, group_data)
                    row = group_result.fetchone()
                    if row:
                        group_id = row[0]
                        group_map[group['name']] = group_id
                        print(f"Group created: {group['name']} (ID: {group_id})")
            except Exception as e:
                print(f"Error creating group {group.get('name', 'unknown')}: {e}")
        
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
            print("Please check your database connection settings and ensure the database server is running.")
            sys.exit(1)
        
        # Drop tables if requested
        if args.drop:
            try:
                drop_tables(engine)
            except Exception as e:
                print(f"Error dropping tables: {e}")
                sys.exit(1)
        
        # Create tables
        try:
            create_tables(engine)
        except Exception as e:
            print(f"Error creating tables: {e}")
            sys.exit(1)

        # Set permissions
        if args.set_permissions:
            try:
                set_user_permissions(engine)
            except Exception as e:
                print(f"Error setting permissions: {e}")
                sys.exit(1)
        
        # Seed database if requested
        if args.seed:
            if not config:
                print("Error: Cannot seed database without valid configuration. Please check your config file.")
                sys.exit(1)
                
            try:
                # If skipping anomalies is requested, patch the generate_mock_anomaly_data function
                if args.skip_anomalies:
                    print("Skipping anomaly data generation as requested")
                    global generate_mock_anomaly_data
                    old_func = generate_mock_anomaly_data
                    def generate_mock_anomaly_data(*args, **kwargs):
                        return []
                
                # Pass the anomaly interval parameter to the seed function
                config['anomaly_interval'] = args.anomaly_interval
                
                seed_database(engine, config)
                
                # Restore the original function if we patched it
                if args.skip_anomalies:
                    generate_mock_anomaly_data = old_func
            except Exception as e:
                print(f"Error seeding database: {e}")
                sys.exit(1)
            
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()