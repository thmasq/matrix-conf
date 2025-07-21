#!/bin/bash

# Script to generate secrets for Matrix deployment
# Run this script when setting up a new deployment

set -e

echo "Generating secrets for Matrix deployment..."

# Check if required files exist
if [ ! -f "docker-compose.yml" ] || [ ! -f "synapse/homeserver.yaml" ] || [ ! -f ".env.example" ]; then
    echo "Error: Required configuration files not found!"
    echo "Make sure you're in the correct directory with all Matrix configuration files."
    exit 1
fi

# Check if secrets are already generated
if ! grep -q "{{" docker-compose.yml synapse/homeserver.yaml .env.example 2>/dev/null; then
    echo "Warning: Secrets appear to already be generated (no placeholders found)"
    read -p "Do you want to regenerate all secrets? This will overwrite existing ones. (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo "Generating cryptographic secrets..."

# Generate secrets
POSTGRES_PASSWORD=$(openssl rand -hex 64)
REGISTRATION_SHARED_SECRET=$(openssl rand -hex 32)
MACAROON_SECRET_KEY=$(openssl rand -hex 32)
FORM_SECRET=$(openssl rand -hex 32)

echo "Replacing placeholders in configuration files..."

# Create working copies
cp docker-compose.yml docker-compose.yml.tmp
cp synapse/homeserver.yaml synapse/homeserver.yaml.tmp
cp .env.example .env.tmp

# Replace placeholders in docker-compose.yml
sed -i "s/{{POSTGRES_PASSWORD}}/$POSTGRES_PASSWORD/g" docker-compose.yml.tmp

# Replace placeholders in synapse/homeserver.yaml
sed -i "s/{{POSTGRES_PASSWORD}}/$POSTGRES_PASSWORD/g" synapse/homeserver.yaml.tmp
sed -i "s/{{REGISTRATION_SHARED_SECRET}}/$REGISTRATION_SHARED_SECRET/g" synapse/homeserver.yaml.tmp
sed -i "s/{{MACAROON_SECRET_KEY}}/$MACAROON_SECRET_KEY/g" synapse/homeserver.yaml.tmp
sed -i "s/{{FORM_SECRET}}/$FORM_SECRET/g" synapse/homeserver.yaml.tmp

# Handle .env file - keep the ADMIN_TOKEN placeholder for manual setup
sed -i "s/{{ADMIN_TOKEN}}/YOUR_ADMIN_TOKEN_HERE/g" .env.tmp

# Move temporary files to final locations
mv docker-compose.yml.tmp docker-compose.yml
mv synapse/homeserver.yaml.tmp synapse/homeserver.yaml
mv .env.tmp .env

echo "Secrets generated and applied successfully!"
echo ""
echo "Generated secrets summary:"
echo "  PostgreSQL password: ✓ Generated (128 chars)"
echo "  Registration shared secret: ✓ Generated (64 chars)"
echo "  Macaroon secret key: ✓ Generated (64 chars)"
echo "  Form secret: ✓ Generated (64 chars)"
echo ""
echo "Files updated:"
echo "  docker-compose.yml"
echo "  synapse/homeserver.yaml"
echo "  .env (created from .env.example)"
echo ""
echo "IMPORTANT NEXT STEPS:"
echo ""
echo "1. Update server names in configuration files:"
echo "   - Replace 'matrix.tantalius.com' with your domain"
echo "   - Replace 'chat.tantalius.com' with your chat subdomain"
echo ""
echo "2. Set up admin token:"
echo "   a. Start your Matrix server: docker-compose up -d"
echo "   b. Create an admin user:"
echo "      docker-compose exec synapse register_new_matrix_user -c /data/homeserver.yaml http://localhost:8008"
echo "   c. Get an access token for the admin user:"
echo ""
echo "   curl -X POST \"https://your.domain.here/_matrix/client/r0/login\" \\"
echo "   -H \"Content-Type: application/json\" \\"
echo "   -d '{"
echo "     \"type\": \"m.login.password\","
echo "     \"user\": \"admin-user\","
echo "     \"password\": \"H34clRyHXePnzBqYkqxPJLGnGVCU2q\""
echo "   }'"
echo ""
echo "   d. Update ADMIN_TOKEN in .env file with the real admin access token"
echo ""
echo "3. Secure your secrets:"
echo "   - Add .env to .gitignore if not already there"
echo "   - Never commit files with real secrets to version control"
echo ""
echo "Your Matrix deployment is ready to start!"
