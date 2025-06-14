#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ENVIRONMENT=""
FORCE=false
GENERATE_VAULT=false
GENERATE_SEED=false

usage() {
    cat << EOF
Usage: $0 [OPTIONS] ENVIRONMENT

Generate configuration files for a new environment

ENVIRONMENT:
    Name of the environment (e.g., campaign_2026, development, staging)

OPTIONS:
    --seed          Generate seed data configuration
    --vault         Generate vault file template
    --all           Generate both seed and vault files
    --force         Overwrite existing files
    -h, --help      Show this help

EXAMPLES:
    $0 --all campaign_2026
    $0 --seed development
    $0 --vault staging --force

NOTE: Generated files will be ignored by git and should be customized before use.

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --seed)
            GENERATE_SEED=true
            shift
            ;;
        --vault)
            GENERATE_VAULT=true
            shift
            ;;
        --all)
            GENERATE_SEED=true
            GENERATE_VAULT=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "Unknown option $1"
            usage
            exit 1
            ;;
        *)
            if [[ -z "$ENVIRONMENT" ]]; then
                ENVIRONMENT="$1"
            else
                echo "Multiple environments specified"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate arguments
if [[ -z "$ENVIRONMENT" ]]; then
    echo "Error: Environment is required"
    usage
    exit 1
fi

if [[ "$GENERATE_SEED" == "false" && "$GENERATE_VAULT" == "false" ]]; then
    echo "Error: Must specify --seed, --vault, or --all"
    usage
    exit 1
fi

# Validate environment name
if [[ ! "$ENVIRONMENT" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Error: Environment name must contain only letters, numbers, underscores, and hyphens"
    exit 1
fi

echo "Generating configuration for environment: $ENVIRONMENT"

# Create directories if they don't exist
mkdir -p "$PROJECT_ROOT/config/environments"
mkdir -p "$PROJECT_ROOT/config/seed-data"
mkdir -p "$PROJECT_ROOT/ansible/vars/$ENVIRONMENT"

# Generate environment configuration
ENV_CONFIG_FILE="$PROJECT_ROOT/config/environments/$ENVIRONMENT.yml"

generate_environment_config() {
    cat > "$ENV_CONFIG_FILE" << EOF
---
# Environment Configuration for $ENVIRONMENT
# Generated on $(date)
# Customize these values for your specific environment

environment:
  name: "$ENVIRONMENT"
  description: "Environment configuration for $ENVIRONMENT"
  
  # Set campaign year if applicable
  # campaign_year: "2026"

database:
  name: "fitonduty_$ENVIRONMENT"
  admin_user: "dashboard_admin"
  app_user: "dashboard_user"
  host: "localhost"
  port: 5432

# Performance settings - adjust based on expected load
performance:
  shared_buffers: "256MB"        # Increase for production (512MB-2GB)
  effective_cache_size: "1GB"    # Set to ~75% of available RAM
  max_connections: 100           # Increase for high-traffic environments
  work_mem: "4MB"               # Increase for complex queries
  maintenance_work_mem: "64MB"   # Increase for maintenance operations

# Write ahead logging
wal:
  level: "replica"
  max_senders: 3
  keep_size: "16MB"

# Features and operational settings
features:
  enable_backup: false           # Set to true for production
  backup_retention_days: 30      # Adjust retention policy
  enable_ssl: false             # Set to true for production
  enable_connection_pooling: false
  debug_mode: false             # Set to true for development environments

# Campaign-specific settings (if applicable)
campaign:
  # data_retention_months: 12
  # participant_limit: 500
  # expected_daily_records: 1000

# Monitoring and logging
monitoring:
  log_connections: false
  log_disconnections: false
  slow_query_log: true
  log_min_duration: 1000        # Log queries taking more than 1 second

# Data generation settings for testing/seeding
data_generation:
  anomaly_interval_minutes: 5
  default_history_days: 60
  generate_anomalies: true

# Security settings
security:
  # allowed_hosts: []           # Specify allowed connection hosts for production
  # require_ssl: false
  pass
EOF
}

# Generate seed data configuration
SEED_CONFIG_FILE="$PROJECT_ROOT/config/seed-data/$ENVIRONMENT-seed.yml"

generate_seed_config() {
    cat > "$SEED_CONFIG_FILE" << EOF
---
# Seed Data Configuration for $ENVIRONMENT
# Generated on $(date)
# Customize this file with your specific users and groups

# Database connection info (will be overridden by command line or environment)
database:
  # Connection details provided externally

# Administrative users
# NOTE: Change all passwords before using in production!
admins:
  - username: "admin"
    password: "CHANGE_ME_admin_password_$(openssl rand -hex 8)"
  - username: "${ENVIRONMENT}_admin"
    password: "CHANGE_ME_${ENVIRONMENT}_admin_$(openssl rand -hex 8)"

# Groups for this environment
groups:
  - name: "$ENVIRONMENT Main Group"
    description: "Primary participant group for $ENVIRONMENT environment"
    created_by: "admin"
  
  # Add more groups as needed
  # - name: "$ENVIRONMENT Test Group"
  #   description: "Testing group for $ENVIRONMENT"
  #   created_by: "admin"

# Sample participants
# Remove or modify these for production environments
participants:
  - username: "demo_participant_$ENVIRONMENT"
    password: "CHANGE_ME_demo_$(openssl rand -hex 6)"
    groups: "$ENVIRONMENT Main Group"
    generate_data: true
    data_days: 60  # 2 months of sample data
  
  - username: "test_user_$ENVIRONMENT"
    password: "CHANGE_ME_test_$(openssl rand -hex 6)"
    groups: "$ENVIRONMENT Main Group"
    generate_data: true
    data_days: 30  # 1 month of sample data

# Additional participants can be added here
# For production, consider adding participants through the admin interface
# rather than including them in seed data

# Development/Testing specific participants
# Uncomment and modify for development environments
# participants:
#   - username: "dev_athlete_$ENVIRONMENT"
#     password: "CHANGE_ME_athlete_$(openssl rand -hex 6)"
#     groups: ["$ENVIRONMENT Main Group"]
#     generate_data: true
#     data_days: 90
#     
#   - username: "dev_beginner_$ENVIRONMENT"
#     password: "CHANGE_ME_beginner_$(openssl rand -hex 6)"
#     groups: "$ENVIRONMENT Main Group"
#     generate_data: true
#     data_days: 45
EOF
}

# Generate Ansible vault template
VAULT_FILE="$PROJECT_ROOT/ansible/vars/$ENVIRONMENT/vault.yml"
MAIN_VARS_FILE="$PROJECT_ROOT/ansible/vars/$ENVIRONMENT/main.yml"

generate_vault_template() {
    # Generate random passwords
    ADMIN_PASS=$(openssl rand -base64 24)
    APP_PASS=$(openssl rand -base64 24)
    POSTGRES_PASS=$(openssl rand -base64 24)
    
    # Create the vault file content (unencrypted for now)
    cat > "${VAULT_FILE}.template" << EOF
---
# Vault file for $ENVIRONMENT environment
# Generated on $(date)
# 
# IMPORTANT: 
# 1. Customize these passwords before use
# 2. Encrypt this file with: ansible-vault encrypt $VAULT_FILE
# 3. Never commit unencrypted vault files to git

# Database passwords
vault_admin_password: "$ADMIN_PASS"
vault_app_password: "$APP_PASS"
vault_postgres_password: "$POSTGRES_PASS"

# Flask keys
vault_flask_key: "$(openssl rand -hex 48)"

# Additional secrets can be added here
# vault_api_secret_key: "$(openssl rand -base64 32)"
# vault_jwt_secret: "$(openssl rand -base64 32)"

# External service credentials (if needed)
# vault_smtp_password: "your_smtp_password"
# vault_api_tokens:
#   service1: "your_service1_token"
#   service2: "your_service2_token"
EOF

    echo "Vault template created at: ${VAULT_FILE}.template"
    echo "To use it:"
    echo "  1. Review and customize the passwords"
    echo "  2. mv '${VAULT_FILE}.template' '$VAULT_FILE'"
    echo "  3. ansible-vault encrypt '$VAULT_FILE'"
}

generate_main_vars() {
    cat > "$MAIN_VARS_FILE" << EOF
---
# Main variables for $ENVIRONMENT environment
# Generated on $(date)

# Environment identification
db_environment: "$ENVIRONMENT"

# Database configuration
fitonduty_db_name: "fitonduty_$ENVIRONMENT"
fitonduty_admin_user: "dashboard_admin"
fitonduty_app_user: "dashboard_user"

# Environment-specific settings
enable_backup: false
enable_ssl: false
debug_mode: false

# Performance tuning (adjust based on server capacity)
postgresql_shared_buffers: "256MB"
postgresql_max_connections: 100
postgresql_effective_cache_size: "1GB"
postgresql_work_mem: "4MB"
postgresql_maintenance_work_mem: "64MB"

# Add additional non-sensitive variables here
EOF
}

# Check if files exist and handle force flag
check_file_exists() {
    local file="$1"
    local type="$2"
    
    if [[ -f "$file" && "$FORCE" == "false" ]]; then
        echo "Warning: $type file already exists: $file"
        echo "Use --force to overwrite"
        return 1
    fi
    return 0
}

# Generate environment config (always generated as it's not sensitive)
if check_file_exists "$ENV_CONFIG_FILE" "Environment config" || [[ "$FORCE" == "true" ]]; then
    generate_environment_config
    echo "✓ Environment config generated: $ENV_CONFIG_FILE"
fi

# Generate seed data config
if [[ "$GENERATE_SEED" == "true" ]]; then
    if check_file_exists "$SEED_CONFIG_FILE" "Seed config" || [[ "$FORCE" == "true" ]]; then
        generate_seed_config
        echo "✓ Seed config generated: $SEED_CONFIG_FILE"
    fi
fi

# Generate vault files
if [[ "$GENERATE_VAULT" == "true" ]]; then
    # Create vars directory
    mkdir -p "$(dirname "$VAULT_FILE")"
    
    if check_file_exists "$VAULT_FILE" "Vault" || [[ "$FORCE" == "true" ]]; then
        generate_vault_template
        echo "✓ Vault template generated: ${VAULT_FILE}.template"
    fi
    
    if check_file_exists "$MAIN_VARS_FILE" "Main vars" || [[ "$FORCE" == "true" ]]; then
        generate_main_vars
        echo "✓ Main vars generated: $MAIN_VARS_FILE"
    fi
fi

echo ""
echo "Configuration generation completed for environment: $ENVIRONMENT"
echo ""
echo "Next steps:"
echo "1. Review and customize the generated files"
echo "2. Update passwords and sensitive information"

if [[ "$GENERATE_VAULT" == "true" ]]; then
    echo "3. Encrypt the vault file:"
    echo "   mv '${VAULT_FILE}.template' '$VAULT_FILE'"
    echo "   ansible-vault encrypt '$VAULT_FILE'"
fi

if [[ "$GENERATE_SEED" == "true" ]]; then
    echo "4. Test the configuration:"
    echo "   ./scripts/setup_environment.sh $ENVIRONMENT"
fi

echo "5. Deploy when ready:"
echo "   ./scripts/deploy.sh $ENVIRONMENT"