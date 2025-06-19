"""
Database migration management
"""

import argparse
import glob
import os
from pathlib import Path
import sys

from sqlalchemy import text

def execute_migrations(engine, migration_path=None):
    """Execute migration files"""
    
    script_dir = Path(__file__).parent
    
    if migration_path:
        migrations_dir = Path(migration_path)
    else:
        migrations_dir = script_dir.parent / "schema" / "migrations"
    
    if not migrations_dir.exists():
        print(f"Migrations directory not found: {migrations_dir}")
        return True  # Not an error if no migrations exist
    
    # Get all .sql files and sort them
    migration_files = sorted(glob.glob(str(migrations_dir / "*.sql")))
    
    if not migration_files:
        print("No migration files found")
        return True
    
    print(f"Found {len(migration_files)} migration files to execute")
    
    try:
        with engine.begin() as conn:
            for migration_file in migration_files:
                filename = os.path.basename(migration_file)
                print(f"Executing migration: {filename}")
                
                with open(migration_file, 'r') as f:
                    sql_content = f.read()
                
                # Split by semicolon and execute each statement
                statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
                
                for statement in statements:
                    if statement:
                        conn.execute(text(statement))
                
                print(f"✓ Executed {filename}")
        
        print("All migrations executed successfully!")
        return True
        
    except Exception as e:
        print(f"Error executing migrations: {e}")
        return False

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Database migration manager')
    parser.add_argument('--db-url', type=str, help='Database URL (takes precedence over config file)')
    parser.add_argument('--config', type=str, help='Configuration file path')
    parser.add_argument('--migration-path', type=str, help='Custom path to migration files')
    
    return parser.parse_args()

if __name__ == "__main__":
    from db_manager import create_db_engine, load_config
    
    args = parse_arguments()
    
    # Determine database URL with command line preference
    db_url = None
    config = None
    
    if args.db_url:
        # Command line --db-url takes precedence
        db_url = args.db_url
        print("Using database URL from command line")
    elif args.config:
        # Load from config file
        config = load_config(args.config)
        if not config:
            print(f"Failed to load configuration from: {args.config}")
            sys.exit(1)
        print(f"Using configuration from: {args.config}")
    else:            
        print("No database URL or config file provided. Please specify one of them.")
        sys.exit(1)
    
    # Create engine with appropriate arguments
    if db_url:
        # Create a mock args object with db_url
        engine_args = type('Args', (), {'db_url': db_url, 'config': None})()
        engine = create_db_engine(engine_args, None)
    else:
        # Use config
        engine_args = type('Args', (), {'db_url': None, 'config': args.config})()
        engine = create_db_engine(engine_args, config)
    
    if not engine:
        print("Failed to create database engine")
        sys.exit(1)
    
    # Execute migrations
    success = execute_migrations(engine, args.migration_path)
    sys.exit(0 if success else 1)