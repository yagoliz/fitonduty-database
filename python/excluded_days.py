"""
Database functions for managing excluded days
"""
from datetime import timedelta, datetime
from pathlib import Path
from typing import List, Dict, Any

from sqlalchemy import text
import yaml


def add_excluded_day(engine, group_id: int, date, reason: str = "No data expected") -> bool:
    """
    Add an excluded day for a group
    
    Args:
        engine: SQLAlchemy engine
        group_id: Group ID
        date: Date to exclude
        reason: Reason for exclusion
        
    Returns:
        bool: True if successful, False otherwise
    """
    
    query = text("""
        INSERT INTO excluded_days (group_id, date, reason)
        VALUES (:group_id, :date, :reason)
        ON CONFLICT (group_id, date) 
        DO UPDATE SET reason = :reason
    """)
    
    try:
        with engine.connect() as conn:
            conn.execute(query, {
                "group_id": group_id,
                "date": date,
                "reason": reason
            })
            conn.commit()
            return True
    except Exception as e:
        print(f"Error adding excluded day: {e}")
        return False


def get_excluded_days(engine, group_id: int, start_date=None, end_date=None) -> List[Dict]:
    """
    Get excluded days for a group
    
    Args:
        engine: SQLAlchemy engine
        group_id: Group ID
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        List of excluded days
    """
    
    base_query = """
        SELECT date, reason FROM excluded_days 
        WHERE group_id = :group_id
    """
    
    params = {"group_id": group_id}
    
    if start_date and end_date:
        base_query += " AND date BETWEEN :start_date AND :end_date"
        params.update({"start_date": start_date, "end_date": end_date})
    
    base_query += " ORDER BY date"
    query = text(base_query)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query, params)
            return [{"date": row.date, "reason": row.reason} for row in result]
    except Exception as e:
        print(f"Error getting excluded days: {e}")
        return []


def remove_excluded_day(engine, group_id: int, date) -> bool:
    """
    Remove an excluded day for a group
    
    Args:
        engine: SQLAlchemy engine
        group_id: Group ID
        date: Date to remove from exclusions
        
    Returns:
        bool: True if successful, False otherwise
    """
    
    query = text("""
        DELETE FROM excluded_days 
        WHERE group_id = :group_id AND date = :date
    """)
    
    try:
        with engine.connect() as conn:
            conn.execute(query, {
                "group_id": group_id,
                "date": date
            })
            conn.commit()
            return True
    except Exception as e:
        print(f"Error removing excluded day: {e}")
        return False


def add_all_saturdays(engine, group_id: int, start_date, end_date) -> int:
    """
    Add all Saturdays in a date range as excluded days
    
    Args:
        engine: SQLAlchemy engine
        group_id: Group ID
        start_date: Start date
        end_date: End date
        
    Returns:
        int: Number of Saturdays added
    """
    current_date = start_date
    added_count = 0
    
    while current_date <= end_date:
        # Check if it's a Saturday (weekday() returns 5 for Saturday)
        if current_date.weekday() == 5:
            if add_excluded_day(engine, group_id, current_date, "Saturday - no data expected"):
                added_count += 1
        current_date += timedelta(days=1)
    
    return added_count


def add_weekly_pattern(engine, group_id: int, start_date, end_date, 
                      excluded_weekdays: List[int], reason: str = "Regular exclusion") -> int:
    """
    Add a weekly pattern of excluded days
    
    Args:
        engine: SQLAlchemy engine
        group_id: Group ID
        start_date: Start date
        end_date: End date
        excluded_weekdays: List of weekday numbers to exclude (0=Monday, 6=Sunday)
        reason: Reason for exclusion
        
    Returns:
        int: Number of days added
    """
    current_date = start_date
    added_count = 0
    
    while current_date <= end_date:
        if current_date.weekday() in excluded_weekdays:
            if add_excluded_day(engine, group_id, current_date, reason):
                added_count += 1
        current_date += timedelta(days=1)
    
    return added_count


def load_exclusion_config(config_file: str) -> Dict[str, Any]:
    """Load exclusion configuration from YAML file"""
    config_path = Path(config_file)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate basic structure
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")
        
        if 'groups' not in config:
            raise ValueError("Configuration must contain 'groups' key")
        
        if not isinstance(config['groups'], list):
            raise ValueError("'groups' must be a list")
        
        return config
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format: {e}")


def apply_exclusion_config(engine, config: Dict[str, Any]):
    """Apply exclusion configuration to database"""
    
    groups_processed = 0
    total_exclusions = 0
    
    for group_config in config.get('groups', []):
        try:
            # Validate required fields
            if 'group_id' not in group_config:
                print("Warning: Skipping group config without group_id")
                continue
            
            if 'start_date' not in group_config or 'end_date' not in group_config:
                print(f"Warning: Skipping group {group_config['group_id']} without start_date or end_date")
                continue
            
            group_id = group_config['group_id']
            start_date = datetime.strptime(group_config['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(group_config['end_date'], '%Y-%m-%d').date()
            
            print(f"Processing group {group_id} ({start_date} to {end_date})...")
            
            # Add Saturday exclusions
            if group_config.get('exclude_saturdays', False):
                count = add_all_saturdays(engine, group_id, start_date, end_date)
                print(f"  Added {count} Saturdays")
                total_exclusions += count
            
            # Add weekly patterns
            for pattern in group_config.get('weekly_patterns', []):
                if 'weekdays' not in pattern:
                    print("  Warning: Skipping weekly pattern without weekdays")
                    continue
                
                weekdays = pattern['weekdays']
                reason = pattern.get('reason', 'Regular exclusion')
                count = add_weekly_pattern(engine, group_id, start_date, end_date, weekdays, reason)
                
                weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                               'Friday', 'Saturday', 'Sunday']
                weekday_str = ', '.join(weekday_names[d] for d in weekdays if 0 <= d <= 6)
                print(f"  Added {count} {weekday_str} days")
                total_exclusions += count
            
            # Add specific dates
            for date_config in group_config.get('specific_dates', []):
                if 'date' not in date_config:
                    print("  Warning: Skipping specific date without date field")
                    continue
                
                date = datetime.strptime(date_config['date'], '%Y-%m-%d').date()
                reason = date_config.get('reason', 'Specific exclusion')
                
                if add_excluded_day(engine, group_id, date, reason):
                    print(f"  Added {date} ({reason})")
                    total_exclusions += 1
                else:
                    print(f"  Failed to add {date}")
            
            groups_processed += 1
            
        except ValueError as e:
            print(f"Error processing group {group_config.get('group_id', 'unknown')}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error processing group {group_config.get('group_id', 'unknown')}: {e}")
            continue
    
    print(f"\nSummary: Processed {groups_processed} groups, added {total_exclusions} total exclusions")