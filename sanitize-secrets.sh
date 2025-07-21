!/bin/bash

# Script to sanitize secrets from Matrix configuration files
# This should be run ONCE before committing to version control

set -e

echo "Sanitizing secrets from Matrix configuration files..."

# Create backup directory with timestamp
BACKUP_DIR="backup-$(date +%Y%m%d-%H%M%S)"
echo "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR/synapse"

# Backup original files
echo "Creating backups..."
cp docker-compose.yml "$BACKUP_DIR/"
cp synapse/homeserver.yaml "$BACKUP_DIR/synapse/"
cp .env.example "$BACKUP_DIR/"

echo "Replacing secrets with placeholders..."

# Replace secrets in docker-compose.yml
sed -i 's/POSTGRES_PASSWORD: [a-f0-9]\{128\}/POSTGRES_PASSWORD: {{POSTGRES_PASSWORD}}/g' docker-compose.yml

# Replace secrets in synapse/homeserver.yaml
sed -i 's/password: [a-f0-9]\{128\}/password: {{POSTGRES_PASSWORD}}/g' synapse/homeserver.yaml
sed -i 's/registration_shared_secret: [a-f0-9]\{64\}/registration_shared_secret: {{REGISTRATION_SHARED_SECRET}}/g' synapse/homeserver.yaml
sed -i 's/macaroon_secret_key: [a-f0-9]\{64\}/macaroon_secret_key: {{MACAROON_SECRET_KEY}}/g' synapse/homeserver.yaml
sed -i 's/form_secret: [a-f0-9]\{64\}/form_secret: {{FORM_SECRET}}/g' synapse/homeserver.yaml

# Replace admin token placeholder in .env.example
sed -i 's/ADMIN_TOKEN=token_for_any_admin_user/ADMIN_TOKEN={{ADMIN_TOKEN}}/g' .env.example

echo "Secrets sanitized successfully!"
echo ""
echo "Summary of placeholders created:"
echo "  {{POSTGRES_PASSWORD}}       - PostgreSQL database password (128 chars)"
echo "  {{REGISTRATION_SHARED_SECRET}} - Synapse registration secret (64 chars)"
echo "  {{MACAROON_SECRET_KEY}}     - Synapse macaroon secret (64 chars)"
echo "  {{FORM_SECRET}}             - Synapse form secret (64 chars)"
echo "  {{ADMIN_TOKEN}}             - Admin user access token (manual)"
echo ""
echo "Backup files created in: $BACKUP_DIR"
echo "  ├── docker-compose.yml"
echo "  ├── .env.example"
echo "  └── synapse/"
echo "      ├── homeserver.yaml"
echo ""
echo "⚠️  IMPORTANT: The {{ADMIN_TOKEN}} must be manually set by users after creating an admin account"
echo "Your configuration is now ready for version control!"
