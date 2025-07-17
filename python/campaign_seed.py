#!/usr/bin/env python3
"""
Campaign Seed Data Generator

This script generates seed data configuration files for FitonDuty campaigns
based on either:
1. Directory structure where root directory contains group folders, 
   and each group folder contains participant folders
2. CSV file with columns: participant_id, group

Usage:
    # From directory structure:
    python generate_campaign_seed.py --directory /path/to/campaign/root campaign_2024
    
    # From CSV file:
    python generate_campaign_seed.py --csv /path/to/participants.csv campaign_2025
"""


import argparse
import csv
from datetime import datetime
from pathlib import Path
import secrets
import string
import sys

import yaml


def generate_password(length=12):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def generate_admin_password(length=16):
    """Generate a secure admin password"""
    return generate_password(length)


def scan_csv_file(csv_path):
    """
    Read participants and groups from CSV file
    
    Args:
        csv_path (str): Path to CSV file with columns: participant_id, group
        
    Returns:
        dict: Dictionary with groups and their participants
    """
    csv_file = Path(csv_path)
    
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")
    
    structure = {}
    
    try:
        with open(csv_file, 'r', newline='', encoding='utf-8') as file:
            # Try to detect if there's a header
            sample = file.read(1024)
            file.seek(0)
            
            # Check if first line looks like a header
            sniffer = csv.Sniffer()
            has_header = sniffer.has_header(sample)
            
            reader = csv.reader(file)
            
            # Skip header if present
            if has_header:
                header = next(reader)
                print(f"📋 Detected CSV header: {header}")
            
            # Read participant data
            for row_num, row in enumerate(reader, start=2 if has_header else 1):
                if len(row) < 2:
                    print(f"Warning: Row {row_num} has insufficient columns, skipping: {row}")
                    continue
                
                # Strip whitespace from values
                participant_id = row[0].strip()
                group_name = row[1].strip()
                
                # Skip empty rows
                if not participant_id or not group_name:
                    print(f"Warning: Row {row_num} has empty values, skipping: {row}")
                    continue
                
                # Add to structure
                if group_name not in structure:
                    structure[group_name] = []
                
                if participant_id not in structure[group_name]:
                    structure[group_name].append(participant_id)
                else:
                    print(f"Warning: Duplicate participant '{participant_id}' in group '{group_name}', skipping")
    
    except Exception as e:
        raise Exception(f"Error reading CSV file: {e}")
    
    return structure


def scan_directory_structure(root_path):
    """
    Scan the directory structure and return groups and participants
    
    Args:
        root_path (str): Path to the root directory containing groups
        
    Returns:
        dict: Dictionary with groups and their participants
    """
    root = Path(root_path)
    
    if not root.exists():
        raise FileNotFoundError(f"Root path does not exist: {root_path}")
    
    if not root.is_dir():
        raise NotADirectoryError(f"Root path is not a directory: {root_path}")
    
    structure = {}
    
    # Get all subdirectories in root (these are groups)
    for group_path in root.iterdir():
        if not group_path.is_dir():
            continue  # Skip files
            
        group_name = group_path.name
        participants = []
        
        # Get all subdirectories in group (these are participants)
        for participant_path in group_path.iterdir():
            if not participant_path.is_dir():
                continue  # Skip files
                
            participant_name = participant_path.name
            participants.append(participant_name)
        
        if participants:  # Only add groups that have participants
            structure[group_name] = participants
        else:
            print(f"Warning: Group '{group_name}' has no participants, skipping...")
    
    return structure


def parse_input_source(args):
    """
    Parse input source based on provided arguments
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        dict: Dictionary with groups and their participants
    """
    if args.csv:
        print(f"📊 Reading participants from CSV file: {args.csv}")
        return scan_csv_file(args.csv)
    elif args.directory:
        print(f"📁 Scanning directory structure: {args.directory}")
        return scan_directory_structure(args.directory)
    else:
        # This shouldn't happen due to argument validation
        raise ValueError("No input source specified")


def create_seed_config(campaign_name, directory_structure, admin_username="admin"):
    """
    Create the seed configuration dictionary
    
    Args:
        campaign_name (str): Name of the campaign (e.g., 'campaign_2024')
        directory_structure (dict): Groups and participants from scanning
        admin_username (str): Username for the admin user
        
    Returns:
        dict: Complete seed configuration
    """
    
    # Generate admin password
    admin_password = generate_admin_password()
    
    # Create configuration structure
    config = {
        'database': {
        },
        'admins': [
            {
                'username': admin_username,
                'password': admin_password
            }
        ],
        'groups': [],
        'supervisors': [],
        'participants': []
    }
    
    # Add groups
    for group_name in directory_structure.keys():
        group_config = {
            'name': group_name,
            'description': f'Participant group for {group_name} in {campaign_name}',
            'created_by': admin_username
        }
        config['groups'].append(group_config)

    # Add supervisors
    for group_name in directory_structure.keys():
        supervisor_config = {
            'username': f'supervisor_{group_name.lower()}',
            'password': generate_password(),
            'groups': group_name,  # Single group assignment
            'role': 'supervisor',
            'generate_data': False,
        }
        config['supervisors'].append(supervisor_config)
    
    # Add participants
    for group_name, participants in directory_structure.items():
        for participant_name in participants:
            # Generate participant password
            participant_password = generate_password()
            
            participant_config = {
                'username': participant_name,
                'password': participant_password,
                'groups': group_name,  # Single group assignment
                'generate_data': False,
            }
            config['participants'].append(participant_config)
    
    return config


def save_seed_config(config, output_path):
    """
    Save the seed configuration to a YAML file
    
    Args:
        config (dict): The seed configuration
        output_path (str): Path where to save the file
    """
    output_file = Path(output_path)
    
    # Create directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Add header comment with generation info
    header_comment = f"""# Seed Data Configuration
# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Campaign: {config.get('database', {}).get('name', 'unknown')}
# 
# IMPORTANT SECURITY NOTES:
# 1. All passwords in this file are auto-generated
# 2. Change admin password before production use
# 3. Keep this file secure and never commit to public repositories
# 4. Consider using vault encryption for production environments
#
# Structure generated from directory scan:
"""
    
    with open(output_file, 'w') as f:
        f.write(header_comment)
        yaml.dump(config, f, default_flow_style=False, indent=2, sort_keys=False)
    
    print(f"✓ Seed configuration saved to: {output_file}")


def print_summary(config, campaign_name):
    """Print a summary of the generated configuration"""
    
    total_groups = len(config['groups'])
    total_participants = len(config['participants'])
    
    print(f"\n📊 Configuration Summary for {campaign_name}:")
    print(f"   └── Admin users: {len(config['admins'])}")
    print(f"   └── Groups: {total_groups}")
    print(f"   └── Participants: {total_participants}")
    
    print("\n🔐 Generated Credentials:")
    for admin in config['admins']:
        print(f"   Admin '{admin['username']}': {admin['password']}")
    
    print("\n📁 Group Structure:")
    for group in config['groups']:
        group_name = group['name']
        group_participants = [p['username'] for p in config['participants'] if p['groups'] == group_name]
        print(f"   📂 {group_name} ({len(group_participants)} participants)")
        for participant in group_participants[:3]:  # Show first 3 participants
            print(f"      └── {participant}")
        if len(group_participants) > 3:
            print(f"      └── ... and {len(group_participants) - 3} more")
    
    print("\n⚠️  SECURITY REMINDER:")
    print("   • Change the admin password before production use")
    print("   • Keep this configuration file secure")
    print("   • Consider encrypting with ansible-vault for production")


def main():
    parser = argparse.ArgumentParser(
        description="Generate FitonDuty campaign seed data from directory structure or CSV file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
INPUT SOURCES (choose one):
  --directory DIR     Directory containing group folders with participant subfolders
  --csv FILE          CSV file with columns: participant_id, group

CSV FORMAT:
  participant_id,group
  p1,Group A
  p2,Group A
  p3,Group B
  p4,Group C

DIRECTORY FORMAT:
  root/
  ├── Group A/
  │   ├── p1/
  │   └── p2/
  └── Group B/
      └── p3/

Examples:
  %(prog)s --directory /data/campaigns/2024 campaign_2024
  %(prog)s --csv participants.csv campaign_2025
  %(prog)s --csv /data/participants.csv campaign_2025 --output /config/campaign_2025_seed.yml
        """
    )
    
    # Input source group (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--directory', '-d',
        help='Root directory containing group folders'
    )
    input_group.add_argument(
        '--csv', '-c',
        help='CSV file with participant_id,group columns'
    )
    
    parser.add_argument(
        'campaign_name',
        help='Name of the campaign (e.g., campaign_2024, campaign_2025)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output file path (default: ./config/seed-data/{campaign_name}_seed.yml)',
        default=None
    )
    
    parser.add_argument(
        '--admin-user',
        help='Admin username (default: admin)',
        default='admin'
    )
    
    parser.add_argument(
        '--data-days',
        type=int,
        help='Number of days of sample data to generate (default: 60)',
        default=60
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be generated without creating files'
    )
    
    args = parser.parse_args()
    
    try:
        # Determine output path
        if args.output:
            output_path = args.output
        else:
            # Default to config/seed-data directory
            script_dir = Path(__file__).parent
            config_dir = script_dir.parent / 'config' / 'seed-data'
            output_path = config_dir / f'{args.campaign_name}_seed.yml'
        
        # Parse input source and get directory structure
        directory_structure = parse_input_source(args)
        
        if not directory_structure:
            print("❌ No groups with participants found in the specified input source")
            sys.exit(1)
        
        print(f"✓ Found {len(directory_structure)} groups")
        
        # Create seed configuration
        print(f"🏗️  Generating seed configuration for {args.campaign_name}")
        config = create_seed_config(
            args.campaign_name, 
            directory_structure, 
            args.admin_user
        )
        
        # Update data_days if specified
        if args.data_days != 60:
            for participant in config['participants']:
                participant['data_days'] = args.data_days
        
        # Print summary
        print_summary(config, args.campaign_name)
        
        if args.dry_run:
            print(f"\n🔍 DRY RUN - Configuration would be saved to: {output_path}")
            print("\nTo actually generate the file, run without --dry-run")
        else:
            # Save configuration
            print("\n💾 Saving configuration...")
            save_seed_config(config, output_path)
            print("\n✅ Campaign seed data generated successfully!")
            print("\nNext steps:")
            print("1. Review the generated file: {output_path}")
            print("2. Customize passwords and settings as needed")
            print("3. Use with setup script: ./scripts/setup_environment.sh {args.campaign_name}")
    
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except NotADirectoryError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()