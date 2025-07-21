# Matrix Server Setup

A complete Matrix homeserver deployment using Docker Compose with Synapse, PostgreSQL, Valkey (Redis), Nginx reverse proxy, and Cinny web client.

## Overview

This repository provides a production-ready Matrix homeserver setup with the following components:

- **Synapse**: Matrix homeserver implementation
- **PostgreSQL**: Primary database storage
- **Valkey**: Redis-compatible cache and session storage
- **Nginx**: Reverse proxy and load balancer
- **Cinny**: Modern Matrix web client
- **Admin Scripts**: Room management and permission tools

### Architecture

- Matrix API server: `matrix.yourdomain.com`
- Web client: `chat.yourdomain.com`
- Federation: Disabled by default for security
- Registration: Disabled (admin-created accounts only)

## Prerequisites

- Docker and Docker Compose installed
- Domain names configured with DNS records
- SSL/TLS certificates (recommended: Cloudflare tunnels or Let's Encrypt)
- Basic understanding of Matrix protocol

## Initial Setup

### 1. Clone and Prepare Repository

```bash
git clone https://github.com/thmasq/matrix-conf
cd matrix-server
```

### 2. Generate Secrets

Run the secret generation script to create cryptographic keys and passwords:

```bash
chmod +x generate-secrets.sh
./generate-secrets.sh
```

This script will:
- Generate PostgreSQL password (128 characters)
- Create Synapse registration shared secret (64 characters)
- Generate macaroon secret key (64 characters)
- Create form secret (64 characters)
- Create `.env` file from template

### 3. Configure Domain Names

Update the following files to replace `matrix.tantalius.com` and `chat.tantalius.com` with your actual domains:

**Files to update:**
- `docker-compose.yml`
- `synapse/homeserver.yaml`
- `nginx/nginx.conf`
- `cinny/config.json`

**Search and replace:**
```bash
# Replace Matrix API domain
find . -type f -name "*.yml" -o -name "*.yaml" -o -name "*.conf" -o -name "*.json" | \
xargs sed -i 's/matrix\.tantalius\.com/matrix.yourdomain.com/g'

# Replace web client domain  
find . -type f -name "*.yml" -o -name "*.yaml" -o -name "*.conf" -o -name "*.json" | \
xargs sed -i 's/chat\.tantalius\.com/chat.yourdomain.com/g'
```

### 4. Configure Admin Contact

Update the admin contact in `synapse/homeserver.yaml`:
```yaml
admin_contact: 'mailto:admin@yourdomain.com'
```

## Deployment

### 1. Start Services

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f synapse
```

### 2. Create Admin User

Create the first admin user account:

```bash
docker-compose exec synapse register_new_matrix_user -c /data/homeserver.yaml http://localhost:8008
```

Follow the prompts to create an admin account with:
- Username (e.g., `admin`)
- Password (secure password)
- Admin privileges (yes)

### 3. Configure Admin Token

Generate an access token for the admin user:

```bash
curl -X POST "https://matrix.yourdomain.com/_matrix/client/r0/login" \
-H "Content-Type: application/json" \
-d '{
  "type": "m.login.password",
  "user": "admin",
  "password": "your_admin_password"
}'
```

Copy the `access_token` from the response and update your `.env` file:
```bash
ADMIN_TOKEN=your_actual_access_token_here
```

Restart the services to apply the token:
```bash
docker-compose restart
```

## SSL/TLS Configuration

### Option 1: Cloudflare Tunnels (what I used)

1. Install `cloudflared`
2. Create tunnels for both domains:
   ```bash
   cloudflared tunnel create matrix-api
   cloudflared tunnel create matrix-chat
   ```
3. Configure tunnel routing:
   ```yaml
   # ~/.cloudflared/config.yml
   tunnels:
     matrix-api:
       credentials-file: /path/to/api-credentials.json
     matrix-chat:
       credentials-file: /path/to/chat-credentials.json
   
   ingress:
     - hostname: matrix.yourdomain.com
       service: http://localhost:80
     - hostname: chat.yourdomain.com  
       service: http://localhost:80
     - service: http_status:404
   ```

### Option 2: Let's Encrypt with Certbot

Add SSL configuration to your Nginx setup and use Certbot to obtain certificates.

## Post-Setup Configuration

### 1. Test Matrix API

```bash
curl https://matrix.yourdomain.com/_matrix/client/versions
```

### 2. Access Web Client

Visit `https://chat.yourdomain.com` to access the Cinny web client.

### 3. Create Additional Users

```bash
docker-compose exec synapse register_new_matrix_user -c /data/homeserver.yaml http://localhost:8008
```

## Administration

### Room Management

Use the provided scripts for room administration:

```bash
# Make scripts executable
chmod +x delete-room.sh fix-permissions.sh

# List all rooms
./delete-room.sh list

# Delete a room
./delete-room.sh delete '#room:matrix.yourdomain.com'

# Fix permissions for Element Call
./fix-permissions.sh fix '#room:matrix.yourdomain.com'

# Fix permissions for all rooms
./fix-permissions.sh fix-all
```

### Admin API Access

Access Synapse admin APIs using your admin token:

```bash
# List users
curl -H "Authorization: Bearer your_admin_token" \
https://matrix.yourdomain.com/_synapse/admin/v2/users

# Get server statistics
curl -H "Authorization: Bearer your_admin_token" \
https://matrix.yourdomain.com/_synapse/admin/v1/statistics/users/media
```

## Security Considerations

### Default Security Settings

- **Federation disabled**: No external server communication
- **Registration disabled**: Admin-only account creation
- **Rate limiting**: Configured for DoS protection
- **Profile privacy**: Limited profile access
- **Media limits**: 50MB upload limit, 32M pixel images

### Recommended Additional Security

1. **Firewall Configuration**:
   ```bash
   # Only allow necessary ports
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw deny 8008/tcp  # Block direct Synapse access
   ```

2. **Regular Updates**:
   ```bash
   # Update container images
   docker-compose pull
   docker-compose up -d
   ```

3. **Backup Strategy**:
   - Database: Regular PostgreSQL dumps
   - Media: Backup `/var/lib/docker/volumes/`
   - Config: Version control (without secrets)

## Troubleshooting

### Service Issues

```bash
# Check service status
docker-compose ps

# View service logs
docker-compose logs synapse
docker-compose logs postgres
docker-compose logs nginx

# Restart specific service
docker-compose restart synapse
```

### Database Issues

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U synapse -d synapse

# Check database size
docker-compose exec postgres psql -U synapse -d synapse -c "SELECT pg_size_pretty(pg_database_size('synapse'));"
```

### Permission Issues

```bash
# Fix Docker volume permissions
sudo chown -R 991:991 synapse/
```

### Federation Issues (if enabled)

```bash
# Test federation
curl https://matrix.yourdomain.com/_matrix/federation/v1/version

# Check signing keys
curl https://matrix.yourdomain.com/_matrix/key/v2/server
```

## Monitoring

### Basic Health Checks

```bash
# Matrix API health
curl -f https://matrix.yourdomain.com/_matrix/client/versions || echo "API down"

# Database health
docker-compose exec postgres pg_isready -U synapse || echo "DB down"

# Check container resources
docker stats --no-stream
```

### Log Monitoring

Logs are configured with rotation:
- **Location**: `synapse/homeserver.log`
- **Rotation**: Daily at midnight
- **Retention**: 3 days

## Maintenance

### Regular Tasks

1. **Update containers** (monthly):
   ```bash
   docker-compose pull && docker-compose up -d
   ```

2. **Database maintenance** (weekly):
   ```bash
   docker-compose exec postgres psql -U synapse -d synapse -c "VACUUM ANALYZE;"
   ```

3. **Media cleanup** (as needed):
   ```bash
   # List media usage
   curl -H "Authorization: Bearer your_admin_token" \
   https://matrix.yourdomain.com/_synapse/admin/v1/statistics/users/media
   ```

4. **Room cleanup** (as needed):
   ```bash
   ./delete-room.sh list
   ./delete-room.sh delete '#unused-room:matrix.yourdomain.com'
   ```

## Configuration Files

- `docker-compose.yml`: Service orchestration
- `synapse/homeserver.yaml`: Synapse configuration
- `nginx/nginx.conf`: Reverse proxy configuration
- `cinny/config.json`: Web client configuration
- `.env`: Environment variables (created from template)

## Support

For Matrix-related issues:
- [Synapse Documentation](https://matrix-org.github.io/synapse/latest/)
- [Matrix Specification](https://spec.matrix.org/)
- [Cinny Documentation](https://github.com/ajbura/cinny)

For deployment issues:
- Check Docker Compose logs
- Verify DNS configuration
- Confirm SSL/TLS setup
- Review firewall settings
