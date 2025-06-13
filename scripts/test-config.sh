#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ANSIBLE_DIR="$PROJECT_ROOT/ansible"

ENVIRONMENT="${1:-testing}"

echo "Testing configuration for environment: $ENVIRONMENT"

cd "$ANSIBLE_DIR"

# Test inventory and variable loading
echo "=== Testing inventory and variables ==="
ansible-inventory -i "inventory/$ENVIRONMENT.yml" --list

echo ""
echo "=== Testing playbook syntax ==="
ansible-playbook -i "inventory/$ENVIRONMENT.yml" playbooks/test.yml --syntax-check

echo ""
echo "=== Running configuration test playbook ==="
ansible-playbook -i "inventory/$ENVIRONMENT.yml" playbooks/test.yml

echo ""
echo "Configuration test completed successfully!"