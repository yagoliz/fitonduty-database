#!/usr/bin/env python3
"""
Script to setup common excluded days (Saturdays, holidays, etc.)
"""

import argparse
from datetime import datetime, timedelta
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from excluded_days import (
    add_excluded_day, 
    get_excluded_days, 
    remove_excluded_day,
    add_all_saturdays,
    add_weekly_pattern
)
from excluded_days import load_exclusion_config, apply_exclusion_config


def create_db_engine(db_url: str):
    """Create database engine"""
    try:
        engine = create_engine(db_url)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Setup excluded days for groups')
    
    # Database connection
    parser.add_argument('--db-url', type=str, 
                       help='Database URL (postgresql://user:pass@host:port/db)')
    parser.add_argument('--config', type=str, 
                       help='Configuration file path (YAML format)')
    
    # Group and date range (required for individual actions)
    parser.add_argument('--group-id', type=int, help='Group ID')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    
    # Action arguments
    parser.add_argument('--add-saturdays', action='store_true', help='Add all Saturdays as excluded days')
    parser.add_argument('--add-weekdays', type=str, help='Add specific weekdays as excluded (comma-separated: 0=Mon,1=Tue,...,6=Sun)')
    parser.add_argument('--add-date', type=str, help='Add specific date as excluded day (YYYY-MM-DD)')
    parser.add_argument('--remove-date', type=str, help='Remove specific date from exclusions (YYYY-MM-DD)')
    parser.add_argument('--reason', type=str, default='No data expected', help='Reason for exclusion')
    parser.add_argument('--list', action='store_true', help='List current excluded days')
    
    # Config file action
    parser.add_argument('--apply-config', action='store_true', help='Apply configuration from config file')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.db_url:
        print("Error: --db-url is required")
        sys.exit(1)
    
    # Create database engine
    engine = create_db_engine(args.db_url)
    
    # Handle config file application
    if args.apply_config:
        if not args.config:
            print("Error: --config is required when using --apply-config")
            sys.exit(1)
        
        try:
            config = load_exclusion_config(args.config)
            apply_exclusion_config(engine, config)
            print("Configuration applied successfully")
        except Exception as e:
            print(f"Error applying configuration: {e}")
            sys.exit(1)
        return
    
    # For individual actions, require group-id and dates
    if not args.group_id:
        print("Error: --group-id is required for individual actions")
        sys.exit(1)
    
    if not args.start_date or not args.end_date:
        print("Error: --start-date and --end-date are required for individual actions")
        sys.exit(1)
    
    # Parse dates
    try:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    except ValueError:
        print("Error: Invalid date format. Use YYYY-MM-DD")
        sys.exit(1)
    
    # List excluded days
    if args.list:
        excluded_days = get_excluded_days(engine, args.group_id, start_date, end_date)
        print(f"Excluded days for group {args.group_id} ({start_date} to {end_date}):")
        if excluded_days:
            for day in excluded_days:
                print(f"  {day['date']}: {day['reason']}")
        else:
            print("  No excluded days found.")
        return
    
    # Add all Saturdays
    if args.add_saturdays:
        count = add_all_saturdays(engine, args.group_id, start_date, end_date)
        print(f"Added {count} Saturdays as excluded days for group {args.group_id}")
    
    # Add specific weekdays
    if args.add_weekdays:
        try:
            weekdays = [int(d.strip()) for d in args.add_weekdays.split(',')]
            # Validate weekdays
            if not all(0 <= d <= 6 for d in weekdays):
                print("Error: Weekdays must be between 0 (Monday) and 6 (Sunday)")
                sys.exit(1)
            
            count = add_weekly_pattern(engine, args.group_id, start_date, end_date, 
                                     weekdays, args.reason)
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                           'Friday', 'Saturday', 'Sunday']
            weekday_str = ', '.join(weekday_names[d] for d in weekdays)
            print(f"Added {count} {weekday_str} days as excluded days for group {args.group_id}")
        except ValueError:
            print("Error: Invalid weekday format. Use comma-separated numbers (0-6)")
            sys.exit(1)
    
    # Add specific date
    if args.add_date:
        try:
            specific_date = datetime.strptime(args.add_date, '%Y-%m-%d').date()
            if add_excluded_day(engine, args.group_id, specific_date, args.reason):
                print(f"Added {specific_date} as excluded day for group {args.group_id}")
            else:
                print(f"Failed to add {specific_date} as excluded day")
        except ValueError:
            print("Error: Invalid date format for --add-date. Use YYYY-MM-DD")
            sys.exit(1)
    
    # Remove specific date
    if args.remove_date:
        try:
            specific_date = datetime.strptime(args.remove_date, '%Y-%m-%d').date()
            if remove_excluded_day(engine, args.group_id, specific_date):
                print(f"Removed {specific_date} from excluded days for group {args.group_id}")
            else:
                print(f"Failed to remove {specific_date} from excluded days")
        except ValueError:
            print("Error: Invalid date format for --remove-date. Use YYYY-MM-DD")
            sys.exit(1)


if __name__ == "__main__":
    main()