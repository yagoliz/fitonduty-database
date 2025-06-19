#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ANSIBLE_DIR="$PROJECT_ROOT/ansible"

# Default values
ENVIRONMENT=""
BRANCH="main"
FORCE_REBUILD="false"  # Make sure it's a string
VAULT_PASSWORD_FILE=""
VERBOSE=""
CHECK_MODE=false

usage() {
    cat << EOF
Usage: $0 [OPTIONS] ENVIRONMENT

Update FitonDuty dashboard on specified environment

ENVIRONMENTS:
    testing         - Testing environment
    campaign_2024   - Campaign 2024 production
    campaign_2025   - Campaign 2025 production

OPTIONS:
    -b, --branch BRANCH     Git branch to deploy (default: main)
    -f, --force-rebuild     Force container rebuild even if no changes
    -c, --check             Run in check mode (dry run)
    -v, --verbose           Verbose output
    --vault-file FILE       Vault password file
    -h, --help              Show this help

EXAMPLES:
    $0 testing
    $0 campaign_2024 --branch develop
    $0 campaign_2025 --force-rebuild

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--branch)
            BRANCH="$2"
            shift 2
            ;;
        -f|--force-rebuild)
            FORCE_REBUILD="true"  # String value
            shift
            ;;
        -c|--check)
            CHECK_MODE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
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
    exit 1
fi

# Check for vault file
VAULT_ARGS=""
if [[ -n "$VAULT_PASSWORD_FILE" ]]; then
    VAULT_ARGS="--vault-password-file $VAULT_PASSWORD_FILE"
elif [[ -f "$PROJECT_ROOT/.vault_pass" ]]; then
    VAULT_ARGS="--vault-password-file $PROJECT_ROOT/.vault_pass"
fi

# Build ansible-playbook command
ANSIBLE_CMD=(
    "ansible-playbook"
    "-i" "$INVENTORY_FILE"
    "$ANSIBLE_DIR/playbooks/update-dashboard.yml"
    "--extra-vars" "dashboard_branch=$BRANCH"
    "--extra-vars" "force_rebuild=$FORCE_REBUILD"
)

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

# Show what we're about to run
echo "Updating dashboard on environment: $ENVIRONMENT"
echo "Branch: $BRANCH"
echo "Force rebuild: $FORCE_REBUILD"
echo ""

# Run the command
exec "${ANSIBLE_CMD[@]}"