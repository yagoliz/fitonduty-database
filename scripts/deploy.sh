#!/bin/bash

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ANSIBLE_DIR="$PROJECT_ROOT/ansible"

# Default values
ENVIRONMENT=""
VAULT_PASSWORD_FILE=""
CHECK_MODE=false
VERBOSE=""
TAGS=""

usage() {
    cat << EOF
Usage: $0 [OPTIONS] ENVIRONMENT

Deploy FitonDuty database infrastructure using Ansible

ENVIRONMENTS:
    testing         - Testing environment
    campaign-2024   - Campaign 2024 production
    campaign-2025   - Campaign 2025 production

OPTIONS:
    -c, --check         Run in check mode (dry run)
    -v, --verbose       Verbose output (-v, -vv, -vvv)
    -t, --tags TAGS     Run only specified tags
    --vault-file FILE   Vault password file
    -h, --help          Show this help

EXAMPLES:
    $0 testing
    $0 campaign-2024 --check
    $0 campaign-2025 --verbose -vv
    $0 testing --tags "postgresql,database"

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
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
        -t|--tags)
            TAGS="$2"
            shift 2
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
    "$ANSIBLE_DIR/playbooks/database.yml"
)

# Add optional arguments
if [[ "$CHECK_MODE" == "true" ]]; then
    ANSIBLE_CMD+=("--check")
fi

if [[ -n "$VERBOSE" ]]; then
    ANSIBLE_CMD+=("$VERBOSE")
fi

if [[ -n "$TAGS" ]]; then
    ANSIBLE_CMD+=("--tags" "$TAGS")
fi

if [[ -n "$VAULT_ARGS" ]]; then
    ANSIBLE_CMD+=($VAULT_ARGS)
fi

# Change to ansible directory
cd "$ANSIBLE_DIR"

# Show what we're about to run
echo "Deploying to environment: $ENVIRONMENT"
echo "Inventory: $INVENTORY_FILE"
echo "Command: ${ANSIBLE_CMD[*]}"
echo ""

# Run the command
exec "${ANSIBLE_CMD[@]}"