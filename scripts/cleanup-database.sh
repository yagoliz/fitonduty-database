# Build ansible-playbook command
ANSIBLE_CMD=(
    "ansible-playbook"
    "-i" "$INVENTORY_FILE"
    "$ANSIBLE_DIR/playbooks/cleanup#!/bin/bash"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ANSIBLE_DIR="$PROJECT_ROOT/ansible"

# Default values
ENVIRONMENT=""
VAULT_PASSWORD_FILE=""
FORCE_CLEANUP=false
SKIP_BACKUP=false
KEEP_FILES=false
KEEP_WORKDIR=false
VERBOSE=""
CHECK_MODE=false

usage() {
    cat << EOF
Usage: $0 [OPTIONS] ENVIRONMENT

⚠️  DANGER: Complete cleanup of FitonDuty database and all related files ⚠️

This script will PERMANENTLY REMOVE:
1. The entire database and all data
2. All database users and permissions
3. Schema files, scripts, and management tools
4. Virtual environment and working directories
5. Backup files and configuration

ENVIRONMENTS:
    testing         - Testing environment
    campaign_2024   - Campaign 2024 production
    campaign_2025   - Campaign 2025 production

OPTIONS:
    --force             Force cleanup without interactive confirmation
    --skip-backup       Skip backup creation (DANGEROUS - not recommended)
    --keep-files        Keep schema files and scripts (only remove database)
    --keep-workdir      Keep working directory structure
    -c, --check         Run in check mode (dry run)
    -v, --verbose       Verbose output (-v, -vv, -vvv)
    --vault-file FILE   Vault password file
    -h, --help          Show this help

SAFETY FEATURES:
    - Interactive confirmation required
    - Automatic backup creation before cleanup
    - Verification of successful cleanup
    - Selective cleanup options

EXAMPLES:
    # Complete cleanup of testing environment
    $0 testing

    # Cleanup database but keep files
    $0 testing --keep-files

    # Force cleanup of production (skips interactive prompt)
    $0 campaign_2024 --force

    # Dry run to see what would be removed
    $0 campaign_2025 --check

⚠️  WARNING: This will destroy ALL database-related components!
    Only use this for complete environment resets or testing cleanup.

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_CLEANUP=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --keep-files)
            KEEP_FILES=true
            shift
            ;;
        --keep-workdir)
            KEEP_WORKDIR=true
            shift
            ;;
        -c|--check)
            CHECK_MODE=true
            shift
            ;;
        -v|--verbose)
            if [[ "$2" =~ ^-v+ ]]; then
                VERBOSE="$2"
                shift 2
            else
                VERBOSE="-v"
                shift
            fi
            ;;
        --vault-file)
            VAULT_PASSWORD_FILE="$2"
            shift 2
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

# Validate environment
if [[ -z "$ENVIRONMENT" ]]; then
    echo "Error: Environment is required"
    usage
    exit 1
fi

INVENTORY_FILE="$ANSIBLE_DIR/inventory/$ENVIRONMENT.yml"
if [[ ! -f "$INVENTORY_FILE" ]]; then
    echo "Error: Inventory file not found: $INVENTORY_FILE"
    echo "Available environments:"
    ls "$ANSIBLE_DIR/inventory/"*.yml 2>/dev/null | xargs -n1 basename | sed 's/.yml$//' | sed 's/^/  /'
    exit 1
fi

# Safety check for production environments
if [[ "$ENVIRONMENT" =~ ^campaign_ && "$CHECK_MODE" != "true" ]]; then
    echo "⚠️  WARNING: You are about to COMPLETELY CLEANUP a PRODUCTION environment: $ENVIRONMENT"
    echo ""
    if [[ "$FORCE_CLEANUP" != "true" ]]; then
        echo "This action requires explicit confirmation."
        echo "If you're sure, add --force to your command:"
        echo "  $0 $ENVIRONMENT --force"
        echo ""
        exit 1
    fi
fi

# Check for vault file
VAULT_ARGS=""
if [[ -n "$VAULT_PASSWORD_FILE" ]]; then
    if [[ ! -f "$VAULT_PASSWORD_FILE" ]]; then
        echo "Error: Vault password file not found: $VAULT_PASSWORD_FILE"
        exit 1
    fi
    VAULT_ARGS="--vault-password-file $VAULT_PASSWORD_FILE"
elif [[ -f "$PROJECT_ROOT/.vault_pass" ]]; then
    VAULT_ARGS="--vault-password-file $PROJECT_ROOT/.vault_pass"
fi

# Build ansible-playbook command
ANSIBLE_CMD=(
    "ansible-playbook"
    "-i" "$INVENTORY_FILE"
    "$ANSIBLE_DIR/playbooks/cleanup-database.yml"
    "--extra-vars" "force_cleanup=true"
)

# Add backup setting
if [[ "$SKIP_BACKUP" == "true" ]]; then
    ANSIBLE_CMD+=("--extra-vars" "create_backup=false")
    echo "⚠️  WARNING: Backup creation disabled!"
fi

# Add file cleanup options
if [[ "$KEEP_FILES" == "true" ]]; then
    ANSIBLE_CMD+=("--extra-vars" "remove_files=false")
    echo "ℹ️  Files will be preserved"
fi

if [[ "$KEEP_WORKDIR" == "true" ]]; then
    ANSIBLE_CMD+=("--extra-vars" "remove_working_dir=false")
    echo "ℹ️  Working directory will be preserved"
fi

# Add optional arguments
if [[ "$CHECK_MODE" == "true" ]]; then
    ANSIBLE_CMD+=("--check")
fi

if [[ -n "$VERBOSE" ]]; then
    ANSIBLE_CMD+=("$VERBOSE")
fi

if [[ -n "$VAULT_ARGS" ]]; then
    ANSIBLE_CMD+=($VAULT_ARGS)
fi

# Change to ansible directory
cd "$ANSIBLE_DIR"

# Final confirmation for non-check mode
if [[ "$CHECK_MODE" != "true" && "$FORCE_CLEANUP" != "true" ]]; then
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                        FINAL WARNING                         ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║ You are about to COMPLETELY DESTROY:                        ║"
    echo "║                                                              ║"
    echo "║ Environment: $ENVIRONMENT"
    printf "║ %-60s ║\n" "Database: YES"
    printf "║ %-60s ║\n" "Users: YES"
    printf "║ %-60s ║\n" "Schema files: $(if [[ "$KEEP_FILES" != "true" ]]; then echo "YES"; else echo "NO"; fi)"
    printf "║ %-60s ║\n" "Working dir: $(if [[ "$KEEP_WORKDIR" != "true" && "$SKIP_BACKUP" == "true" ]]; then echo "YES"; else echo "NO"; fi)"
    printf "║ %-60s ║\n" "Backup: $(if [[ "$SKIP_BACKUP" != "true" ]]; then echo "YES"; else echo "NO (DANGEROUS)"; fi)"
    echo "║                                                              ║"
    echo "║ This action is IRREVERSIBLE without a backup!               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    read -p "Type 'DELETE EVERYTHING' to confirm: " confirmation
    
    if [[ "$confirmation" != "DELETE EVERYTHING" ]]; then
        echo "Operation cancelled."
        exit 1
    fi
fi

# Show what we're about to run
echo ""
echo "Starting complete database cleanup for environment: $ENVIRONMENT"
echo "Backup enabled: $(if [[ "$SKIP_BACKUP" != "true" ]]; then echo "YES"; else echo "NO"; fi)"
echo "Remove files: $(if [[ "$KEEP_FILES" != "true" ]]; then echo "YES"; else echo "NO"; fi)"
echo "Remove workdir: $(if [[ "$KEEP_WORKDIR" != "true" && "$SKIP_BACKUP" == "true" ]]; then echo "YES"; else echo "NO"; fi)"
echo "Check mode: $(if [[ "$CHECK_MODE" == "true" ]]; then echo "YES"; else echo "NO"; fi)"
echo ""

# Run the command
echo "Executing: ${ANSIBLE_CMD[*]}"
echo ""

exec "${ANSIBLE_CMD[@]}"