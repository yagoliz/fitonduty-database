"""
Database function management
"""

import argparse
import glob
import os
from pathlib import Path
import sys

from sqlalchemy import text


def clean_all_functions(engine):
    """Drop all user-defined functions to avoid ownership conflicts"""
    
    print("Cleaning all existing user-defined functions...")
    
    cleanup_sql = """
    DO $$ 
    DECLARE 
        r RECORD;
    BEGIN
        -- Drop all functions in the public schema
        FOR r IN (
            SELECT 
                p.proname,
                pg_get_function_identity_arguments(p.oid) as identity_args
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public'
            AND p.prokind = 'f' -- Only regular functions
        ) 
        LOOP
            BEGIN
                EXECUTE 'DROP FUNCTION IF EXISTS public.' || quote_ident(r.proname) || '(' || r.identity_args || ') CASCADE';
                RAISE NOTICE 'Dropped function: %(%)', r.proname, r.identity_args;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Could not drop function: %(%)', r.proname, r.identity_args;
            END;
        END LOOP;
    END $$;
    """
    
    try:
        with engine.begin() as conn:
            conn.execute(text(cleanup_sql))
        print("✓ Cleaned up all existing functions")
        return True
    except Exception as e:
        print(f"Warning: Could not clean up functions: {e}")
        return True  # Don't fail the whole process
    

def execute_function_files(engine):
    """Execute all function files"""
    
    # Get the functions directory
    script_dir = Path(__file__).parent
    functions_dir = script_dir.parent / "schema" / "functions"
    
    if not functions_dir.exists():
        print(f"Functions directory not found: {functions_dir}")
        return True  # Not an error if no functions exist
    
    # Get all .sql files
    function_files = sorted(glob.glob(str(functions_dir / "*.sql")))
    
    if not function_files:
        print("No function files found")
        return True
    
    print(f"Found {len(function_files)} function files to execute")
    
    # Clean all existing functions first
    clean_all_functions(engine)
    
    try:
        with engine.begin() as conn:
            for function_file in function_files:
                filename = os.path.basename(function_file)
                print(f"Executing function file: {filename}")
                
                with open(function_file, 'r') as f:
                    sql_content = f.read()
                
                # Execute the function creation
                conn.execute(text(sql_content))
                print(f"✓ Executed {filename}")
        
        print("All function files executed successfully!")
        return True
        
    except Exception as e:
        print(f"Error executing function files: {e}")
        return False
    

def deploy_functions(engine, function_path=None):
    """Deploy database functions from SQL files"""
    
    script_dir = Path(__file__).parent
    
    if function_path:
        functions_dir = Path(function_path)
    else:
        functions_dir = script_dir.parent / "schema" / "functions"
    
    if not functions_dir.exists():
        print(f"Functions directory not found: {functions_dir}")
        return True  # Not an error if no functions exist
    
    # Get all .sql files and sort them
    function_files = sorted(glob.glob(str(functions_dir / "*.sql")))
    
    if not function_files:
        print("No function files found")
        return True
    
    print(f"Found {len(function_files)} function files to deploy")
    
    # Clean all existing functions first
    clean_all_functions(engine)
    
    try:
        with engine.begin() as conn:
            for function_file in function_files:
                filename = os.path.basename(function_file)
                print(f"Deploying function: {filename}")
                
                with open(function_file, 'r') as f:
                    sql_content = f.read()
                
                # Execute the function definition
                if sql_content.strip():
                    conn.execute(text(sql_content))
                
                print(f"✓ Deployed {filename}")
        
        print("All functions deployed successfully!")
        return True
        
    except Exception as e:
        print(f"Error deploying functions: {e}")
        return False
    

def list_functions(engine):
    """List all user-defined functions in the database"""
    
    try:
        with engine.begin() as conn:
            # Query to get user-defined functions (PostgreSQL specific)
            query = text("""
                SELECT 
                    n.nspname as schema_name,
                    p.proname as function_name,
                    pg_get_function_arguments(p.oid) as arguments,
                    pg_get_function_result(p.oid) as return_type,
                    CASE 
                        WHEN p.prokind = 'a' THEN 'aggregate'
                        WHEN p.prokind = 'w' THEN 'window'
                        WHEN p.prorettype = 'pg_catalog.trigger'::pg_catalog.regtype THEN 'trigger'
                        WHEN p.prokind = 'p' THEN 'procedure'
                        ELSE 'function'
                    END as function_type
                FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                AND n.nspname NOT LIKE 'pg_temp_%'
                AND n.nspname NOT LIKE 'pg_toast_temp_%'
                ORDER BY n.nspname, p.proname;
            """)
            
            result = conn.execute(query)
            functions = result.fetchall()
            
            if not functions:
                print("No user-defined functions found in the database")
                return True
            
            print(f"\nFound {len(functions)} user-defined functions:")
            print("-" * 80)
            print(f"{'Schema':<15} {'Function':<25} {'Type':<10} {'Arguments':<30}")
            print("-" * 80)
            
            for func in functions:
                schema_name = func.schema_name
                function_name = func.function_name
                function_type = func.function_type
                arguments = func.arguments or "()"
                
                # Truncate long arguments for display
                if len(arguments) > 28:
                    arguments = arguments[:25] + "..."
                
                print(f"{schema_name:<15} {function_name:<25} {function_type:<10} {arguments:<30}")
            
            print("-" * 80)
            return True
            
    except Exception as e:
        print(f"Error listing functions: {e}")
        return False

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Database function manager')
    parser.add_argument('--db-url', type=str, help='Database URL (takes precedence over config file)')
    parser.add_argument('--config', type=str, help='Configuration file path')
    parser.add_argument('--function-path', type=str, help='Custom path to function files')
    parser.add_argument('action', choices=['deploy', 'list'], help='Action to perform')
    
    return parser.parse_args()

def main():
    """Main function for function manager"""
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
    
    # Execute the requested action
    success = False
    
    if args.action == 'deploy':
        success = deploy_functions(engine, args.function_path)
    elif args.action == 'list':
        success = list_functions(engine)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()