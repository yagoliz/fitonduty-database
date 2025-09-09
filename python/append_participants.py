#!/usr/bin/env python3
"""
Append New Participants to Seed File

This script safely appends new participants to an existing campaign seed file
without overwriting existing data.

Usage:
    # From CSV file:
    python append_participants.py --csv new_participants.csv --seed-file ../config/seed-data/campaign_2025_seed.yml
    
    # Interactive mode:
    python append_participants.py --interactive --seed-file ../config/seed-data/campaign_2025_seed.yml

CSV format:
    participant_id,group
    FOD111,Colombier
    FOD112,Thun
"""

import argparse
import csv
import secrets
import string
import sys

import yaml


def generate_password(length=12):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def load_seed_file(seed_file_path):
    """Load existing seed file"""
    try:
        with open(seed_file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Seed file not found: {seed_file_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        sys.exit(1)


def get_existing_participant_ids(seed_data):
    """Extract existing participant usernames to avoid duplicates"""
    existing_ids = set()
    if 'participants' in seed_data:
        for participant in seed_data['participants']:
            existing_ids.add(participant['username'])
    return existing_ids


def get_existing_groups(seed_data):
    """Extract existing group names"""
    existing_groups = set()
    if 'groups' in seed_data:
        for group in seed_data['groups']:
            existing_groups.add(group['name'])
    return existing_groups


def get_next_participant_number(existing_ids):
    """Find the next available FOD number"""
    numbers = []
    for pid in existing_ids:
        if pid.startswith('FOD') and len(pid) == 6 and pid[3:].isdigit():
            numbers.append(int(pid[3:]))
    
    return max(numbers) + 1 if numbers else 1


def read_participants_from_csv(csv_path):
    """Read participants from CSV file"""
    participants = []
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Clean whitespace
                participant_id = row['participant_id'].strip()
                group = row['group'].strip()
                participants.append({'id': participant_id, 'group': group})
    except FileNotFoundError:
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: Missing column in CSV: {e}")
        print("CSV must have columns: participant_id, group")
        sys.exit(1)
    
    return participants


def interactive_input():
    """Get participant data interactively"""
    participants = []
    print("Enter participants (press Enter with empty participant_id to finish):")
    
    while True:
        participant_id = input("Participant ID (e.g., FOD111): ").strip()
        if not participant_id:
            break
        
        group = input("Group name: ").strip()
        if not group:
            print("Group name cannot be empty")
            continue
        
        participants.append({'id': participant_id, 'group': group})
        print(f"Added: {participant_id} -> {group}")
    
    return participants


def validate_participants(new_participants, existing_ids, existing_groups):
    """Validate new participants data"""
    errors = []
    
    for participant in new_participants:
        pid = participant['id']
        group = participant['group']
        
        # Check for duplicates
        if pid in existing_ids:
            errors.append(f"Participant {pid} already exists in seed file")
        
        # Check participant ID format (optional)
        if not pid.startswith('FOD'):
            print(f"Warning: {pid} doesn't follow FOD### format")
        
        # Check if group exists
        if group not in existing_groups:
            print(f"Warning: Group '{group}' doesn't exist in seed file. You may need to add it manually.")
    
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


def append_participants_to_seed(seed_data, new_participants):
    """Append new participants to seed data"""
    if 'participants' not in seed_data:
        seed_data['participants'] = []
    
    for participant in new_participants:
        participant_entry = {
            'username': participant['id'],
            'password': generate_password(),
            'groups': participant['group'],
            'generate_data': False
        }
        seed_data['participants'].append(participant_entry)
    
    return seed_data


def save_seed_file(seed_data, seed_file_path, backup=True):
    """Save updated seed file with optional backup"""
    if backup:
        backup_path = f"{seed_file_path}.backup"
        print(f"Creating backup: {backup_path}")
        with open(seed_file_path, 'r') as original:
            with open(backup_path, 'w') as backup_file:
                backup_file.write(original.read())
    
    try:
        with open(seed_file_path, 'w') as f:
            yaml.dump(seed_data, f, default_flow_style=False, sort_keys=False, 
                     allow_unicode=True, width=float('inf'))
        print(f"Updated seed file: {seed_file_path}")
    except Exception as e:
        print(f"Error saving seed file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Append new participants to campaign seed file')
    parser.add_argument('--csv', help='Path to CSV file with new participants')
    parser.add_argument('--interactive', action='store_true', help='Interactive input mode')
    parser.add_argument('--seed-file', required=True, help='Path to campaign seed YAML file')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating backup file')
    
    args = parser.parse_args()
    
    if not args.csv and not args.interactive:
        print("Error: Must specify either --csv or --interactive")
        sys.exit(1)
    
    if args.csv and args.interactive:
        print("Error: Cannot use both --csv and --interactive")
        sys.exit(1)
    
    # Load existing seed file
    print(f"Loading seed file: {args.seed_file}")
    seed_data = load_seed_file(args.seed_file)
    
    # Get existing data
    existing_ids = get_existing_participant_ids(seed_data)
    existing_groups = get_existing_groups(seed_data)
    
    print(f"Found {len(existing_ids)} existing participants")
    print(f"Found {len(existing_groups)} existing groups: {', '.join(existing_groups)}")
    
    # Get new participants
    if args.csv:
        print(f"Reading participants from CSV: {args.csv}")
        new_participants = read_participants_from_csv(args.csv)
    else:
        new_participants = interactive_input()
    
    if not new_participants:
        print("No participants to add")
        sys.exit(0)
    
    print(f"\nNew participants to add: {len(new_participants)}")
    for p in new_participants:
        print(f"  - {p['id']} -> {p['group']}")
    
    # Validate new participants
    if not validate_participants(new_participants, existing_ids, existing_groups):
        sys.exit(1)
    
    # Confirm before proceeding
    if input("\nProceed with adding participants? (y/N): ").lower() != 'y':
        print("Cancelled")
        sys.exit(0)
    
    # Append participants
    updated_seed_data = append_participants_to_seed(seed_data, new_participants)
    
    # Save updated seed file
    save_seed_file(updated_seed_data, args.seed_file, backup=not args.no_backup)
    
    print(f"\nSuccessfully added {len(new_participants)} participants to seed file")
    print("\nNext steps:")
    print("1. Review the updated seed file")
    print("2. Run: python python/db_manager.py --drop --seed --config config/environments/campaign_2025.yml")
    print("3. Or deploy: ./scripts/deploy.sh campaign_2025")


if __name__ == '__main__':
    main()