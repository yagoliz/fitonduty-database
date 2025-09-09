#!/usr/bin/env python3
"""
Add New Participants to Live Database from Seed File

This script reads participants from a seed YAML file and adds only those
that don't already exist in the database, preserving existing data.

Usage:
    python add_participants_live.py --seed-file ../config/seed-data/campaign_2025_seed.yml --config ../config/environments/campaign_2025.yml
    
    # Or with direct database URL:
    python add_participants_live.py --seed-file ../config/seed-data/campaign_2025_seed.yml --db-url postgresql://user:pass@host:port/db
"""

import argparse
import sys
import os

from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash
import yaml


def load_config(config_path):
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Configuration file not found: {config_path}")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return None


def load_seed_file(seed_file_path):
    """Load seed file and extract participants"""
    try:
        with open(seed_file_path, 'r') as f:
            seed_data = yaml.safe_load(f)
        
        if 'participants' not in seed_data:
            print("Error: No participants section found in seed file")
            return None, None
        
        participants = seed_data['participants']
        groups_data = seed_data.get('groups', [])
        
        return participants, groups_data
        
    except FileNotFoundError:
        print(f"Error: Seed file not found: {seed_file_path}")
        return None, None
    except yaml.YAMLError as e:
        print(f"Error parsing seed file: {e}")
        return None, None


def create_db_engine(args):
    """Create database engine from args and config"""
    if args.db_url:
        print(f"Using database URL from command line")
        return create_engine(args.db_url)
    
    if args.config:
        config = load_config(args.config)
        if config and 'database' in config:
            db_config = config['database']
            
            if 'url' in db_config:
                return create_engine(db_config['url'])
            
            # Build connection string from components
            host = db_config.get('host', 'localhost')
            port = db_config.get('port', 5432)
            name = db_config.get('name', 'fitonduty_campaign_2025')
            user = db_config.get('admin_user', 'dashboard_admin')
            
            # Try to get password from environment or config
            password = os.environ.get('DB_ADMIN_PASSWORD')
            if not password:
                password = input(f"Enter password for database user '{user}': ")
            
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{name}"
            return create_engine(db_url)
    
    print("Error: Must provide either --config or --db-url")
    sys.exit(1)


def get_existing_data(engine):
    """Get existing participants and groups from database"""
    try:
        with engine.connect() as conn:
            # Get existing participant usernames
            result = conn.execute(text("""
                SELECT username FROM users WHERE role = 'participant'
            """))
            existing_participants = {row[0] for row in result}
            
            # Get existing groups with their IDs
            result = conn.execute(text("""
                SELECT id, group_name FROM groups
            """))
            existing_groups = {row[1]: row[0] for row in result}
            
            return existing_participants, existing_groups
            
    except Exception as e:
        print(f"Error querying database: {e}")
        sys.exit(1)


def filter_new_participants(seed_participants, existing_participants):
    """Filter out participants that already exist in database"""
    new_participants = []
    existing_count = 0
    
    for participant in seed_participants:
        username = participant['username']
        if username in existing_participants:
            existing_count += 1
            print(f"  ⏭️  Skipping {username} (already exists)")
        else:
            new_participants.append(participant)
    
    print(f"Found {len(seed_participants)} participants in seed file")
    print(f"Skipping {existing_count} existing participants")
    print(f"Will add {len(new_participants)} new participants")
    
    return new_participants


def create_missing_groups(engine, seed_groups_data, existing_groups):
    """Create any missing groups from seed file"""
    if not seed_groups_data:
        return existing_groups
    
    missing_groups = []
    for group_data in seed_groups_data:
        group_name = group_data['name']
        if group_name not in existing_groups:
            missing_groups.append(group_data)
    
    if not missing_groups:
        return existing_groups
    
    print(f"\nCreating {len(missing_groups)} missing groups...")
    
    try:
        with engine.begin() as conn:
            # Get admin user ID for created_by field
            admin_result = conn.execute(text("""
                SELECT id FROM users WHERE role = 'admin' LIMIT 1
            """))
            admin_id = admin_result.scalar()
            
            if not admin_id:
                print("Error: No admin user found in database")
                sys.exit(1)
            
            for group_data in missing_groups:
                group_name = group_data['name']
                description = group_data.get('description', f'Participant group for {group_name}')
                campaign_start_date = group_data.get('campaign_start_date', 'CURRENT_DATE')
                
                # Create group
                result = conn.execute(text("""
                    INSERT INTO groups (group_name, description, created_by, campaign_start_date)
                    VALUES (:group_name, :description, :created_by, :campaign_start_date)
                    RETURNING id
                """), {
                    'group_name': group_name,
                    'description': description,
                    'created_by': admin_id,
                    'campaign_start_date': campaign_start_date
                })
                
                group_id = result.scalar()
                existing_groups[group_name] = group_id
                print(f"  ✓ Created group: {group_name}")
        
        return existing_groups
        
    except Exception as e:
        print(f"Error creating groups: {e}")
        sys.exit(1)


def add_participants_to_database(engine, new_participants, existing_groups):
    """Add new participants to the database using passwords from seed file"""
    if not new_participants:
        print("No new participants to add")
        return
    
    print(f"\nAdding {len(new_participants)} participants to database...")
    
    try:
        with engine.begin() as conn:
            for participant in new_participants:
                username = participant['username']
                password = participant['password']
                group_name = participant['groups']  # Note: 'groups' field in seed file
                
                # Hash the password from seed file
                password_hash = generate_password_hash(password)
                
                # Get group ID
                if group_name not in existing_groups:
                    print(f"Error: Group '{group_name}' not found for participant {username}")
                    continue
                
                group_id = existing_groups[group_name]
                
                # Insert user
                user_result = conn.execute(text("""
                    INSERT INTO users (username, password_hash, role, is_active)
                    VALUES (:username, :password_hash, 'participant', TRUE)
                    RETURNING id
                """), {
                    'username': username,
                    'password_hash': password_hash
                })
                
                user_id = user_result.scalar()
                
                # Add to group
                conn.execute(text("""
                    INSERT INTO user_groups (user_id, group_id)
                    VALUES (:user_id, :group_id)
                """), {
                    'user_id': user_id,
                    'group_id': group_id
                })
                
                print(f"  ✓ Added {username} -> {group_name}")
        
        print(f"\n✅ Successfully added {len(new_participants)} participants!")
        
    except Exception as e:
        print(f"Error adding participants: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Add new participants to live database from seed file')
    parser.add_argument('--seed-file', required=True, help='Path to seed YAML file')
    parser.add_argument('--config', help='Path to configuration YAML file')
    parser.add_argument('--db-url', help='Database connection URL (overrides config)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    if not args.config and not args.db_url:
        print("Error: Must specify either --config or --db-url")
        sys.exit(1)
    
    # Load seed file
    print(f"Loading seed file: {args.seed_file}")
    seed_participants, seed_groups = load_seed_file(args.seed_file)
    if seed_participants is None:
        sys.exit(1)
    
    # Create database connection
    engine = create_db_engine(args)
    
    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)
    
    # Get existing data
    existing_participants, existing_groups = get_existing_data(engine)
    print(f"Found {len(existing_participants)} existing participants in database")
    print(f"Found {len(existing_groups)} existing groups: {', '.join(existing_groups.keys())}")
    
    # Filter out existing participants
    new_participants = filter_new_participants(seed_participants, existing_participants)
    
    if not new_participants:
        print("\n✅ All participants from seed file already exist in database")
        sys.exit(0)
    
    print(f"\nNew participants to add:")
    for p in new_participants:
        print(f"  - {p['username']} -> {p['groups']}")
    
    if args.dry_run:
        print("\n🔍 DRY RUN - No changes will be made")
        print("Would create missing groups and add participants as shown above")
        sys.exit(0)
    
    # Confirm before proceeding
    if input(f"\nProceed with adding {len(new_participants)} participants to the live database? (y/N): ").lower() != 'y':
        print("Cancelled")
        sys.exit(0)
    
    # Create missing groups from seed file
    updated_groups = create_missing_groups(engine, seed_groups, existing_groups)
    
    # Add participants
    add_participants_to_database(engine, new_participants, updated_groups)


if __name__ == '__main__':
    main()