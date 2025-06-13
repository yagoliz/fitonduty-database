#!/bin/bash

ENVIRONMENT=${1:-testing}
CONFIG_DIR="$(dirname "$0")/../config"
PYTHON_DIR="$(dirname "$0")/../python"

echo "Setting up environment: $ENVIRONMENT"

# Check if environment config exists
if [[ ! -f "$CONFIG_DIR/environments/$ENVIRONMENT.yml" ]]; then
    echo "Error: Environment config not found: $ENVIRONMENT.yml"
    echo "Available environments:"
    ls "$CONFIG_DIR/environments/"*.yml 2>/dev/null | xargs -n1 basename | sed 's/.yml$//'
    exit 1
fi

# Check if seed data exists
if [[ ! -f "$CONFIG_DIR/seed-data/$ENVIRONMENT-seed.yml" ]]; then
    echo "Error: Seed data not found: $ENVIRONMENT-seed.yml"
    exit 1
fi

echo "Using config: $CONFIG_DIR/environments/$ENVIRONMENT.yml"
echo "Using seed data: $CONFIG_DIR/seed-data/$ENVIRONMENT-seed.yml"

# Run database setup
uv run "$PYTHON_DIR/db_manager.py" \
    --config "$CONFIG_DIR/seed-data/$ENVIRONMENT-seed.yml" \
    --seed \
    --set-permissions

echo "Environment $ENVIRONMENT setup complete!"