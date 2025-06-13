import os
import sys
import psycopg2
import argparse
import glob
from dotenv import load_dotenv

def load_sql_file(file_path):
    """Load SQL from a file"""
    with open(file_path, 'r') as f:
        return f.read()

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Update database functions')
    parser.add_argument('--db-url', help='Database connection URL for admin')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Use provided URL or environment variable
    db_url = args.db_url or os.environ.get('DASHBOARD_ADMIN_DB_URL')
    
    if not db_url:
        print("Error: Database URL not provided. Use --db-url or set DASHBOARD_ADMIN_DB_URL environment variable.")
        print("Make sure you've created a .env file or set the environment variable.")
        return 1
    
    try:
        # Connect to database as admin
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        
        print("Connected to database as dashboard_admin")
        
        # Get all SQL function files
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        sql_dir = os.path.join(project_root, 'schema', 'functions')
        
        if not os.path.exists(sql_dir):
            print(f"SQL functions directory not found: {sql_dir}")
            print("Creating directory...")
            os.makedirs(sql_dir, exist_ok=True)
            print(f"Created directory: {sql_dir}")
            return 0
        
        sql_files = glob.glob(os.path.join(sql_dir, '*.sql'))
        
        if not sql_files:
            print(f"No SQL function files found in {sql_dir}")
            return 0
        
        # Execute each SQL function file
        for sql_file in sql_files:
            file_name = os.path.basename(sql_file)
            print(f"Processing {file_name}...")
            
            sql_content = load_sql_file(sql_file)
            
            with conn.cursor() as cur:
                try:
                    cur.execute(sql_content)
                    print(f"Successfully updated function from {file_name}")
                except Exception as e:
                    print(f"Error executing {file_name}: {e}")
                    print("SQL content:")
                    print(sql_content[:500] + "..." if len(sql_content) > 500 else sql_content)
        
        print("All functions processed")
        return 0
        
    except Exception as e:
        print(f"Database connection error: {e}")
        return 1
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == '__main__':
    sys.exit(main())