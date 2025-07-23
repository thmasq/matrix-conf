# Matrix Server Setup

A complete Matrix homeserver deployment using Docker Compose with Synapse, PostgreSQL, Valkey (Redis), Nginx reverse proxy, and Cinny web client.

## Overview

This repository provides a production-ready Matrix homeserver setup with the following components:

- **Synapse**: Matrix homeserver implementation
- **PostgreSQL**: Primary database storage
- **Valkey**: Redis-compatible cache and session storage
- **Nginx**: Reverse proxy and load balancer
- **Cinny**: Modern Matrix web client
- **Admin Tool**: Python-based administration interface

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
- Python 3.6+ (for administration tool)

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
- `homeserver.yaml`
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

### 4. Configure Admin Contact (Optional)

Update the admin contact in `homeserver.yaml`:
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

### Matrix Administration Tool

The repository includes a comprehensive Python-based administration tool (`admin.py`) that provides an interactive interface for managing your Matrix server.

#### Features

**Room Management:**
- List all rooms with filtering and sorting capabilities
- Delete rooms with interactive selection and batch operations
- Fix room permissions for Element Call compatibility

**User Management:**
- List all users with filtering and sorting
- Create new users with admin privileges
- Deactivate users with interactive selection and batch operations

**Server Information:**
- Display server statistics (users, rooms, media usage)
- Test server connection and admin token validity

#### Setup and Usage

1. **Run the administration tool:**
   ```bash
   python3 admin.py
   ```

2. **First-time setup:**
   - The tool will automatically load configuration from your `.env` file
   - If configuration is missing, it will prompt for homeserver URL and admin token
   - Test connection will verify your setup

3. **Navigation:**
   - Use the numbered menu options to navigate
   - Filter and sort lists using interactive prompts
   - Select multiple items using ranges (e.g., `1-5,7,9-12`)
   - Use pagination controls for large lists

#### Example Operations

**List and filter rooms:**
```bash
# Run admin tool
python3 admin.py

# Select option 1 (List all rooms)
# Use 'f' to filter by name, alias, member count, etc.
# Use 's' to sort by various criteria
```

**Delete multiple rooms:**
```bash
# Select option 2 (Delete room)
# Choose option 1 (Select from list)
# Filter/sort as needed, then select rooms: "1,3-5,7"
# Confirm deletion and monitor progress
```

**Batch user management:**
```bash
# Select option 6 (Deactivate user)
# Choose option 1 (Select from list)
# Filter users and select multiple: "2-4,8"
# Confirm deactivation
```

### Admin API Access

Access Synapse admin APIs directly using your admin token:

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

### Administration Tool Issues

```bash
# Test admin tool connection
python3 admin.py
# Select option 8 (Test connection)

# Check admin token validity
curl -H "Authorization: Bearer your_admin_token" \
https://matrix.yourdomain.com/_matrix/client/r0/account/whoami
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
   Use the admin tool (option 7) to check media usage statistics, or query directly:
   ```bash
   curl -H "Authorization: Bearer your_admin_token" \
   https://matrix.yourdomain.com/_synapse/admin/v1/statistics/users/media
   ```

4. **Room cleanup** (as needed):
   ```bash
   # Use admin tool for interactive management
   python3 admin.py
   # Select option 1 to list rooms, then option 2 to delete unused rooms
   ```

## Configuration Files

- `docker-compose.yml`: Service orchestration
- `homeserver.yaml`: Synapse configuration
- `nginx/nginx.conf`: Reverse proxy configuration
- `cinny/config.json`: Web client configuration
- `.env`: Environment variables (created from template)
- `admin.py`: Administration tool

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
- Use the admin tool for server diagnostics
