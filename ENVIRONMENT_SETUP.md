# Environment Setup Guide

## Security-First Setup (Recommended)

This setup keeps secrets out of git while maintaining compatibility with all services.

### Development Setup

1. Copy the example file and customize:

   ```bash
   cp .dev.env.example .dev.env
   # Edit .dev.env with your development values
   ```

2. Start development environment:

   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.develop.yml up -d
   ```

### VS Code Dev Container Setup

For a complete VS Code development environment with IntelliSense, debugging, and extensions:

1. Ensure you have the `.dev.env` file (see Development Setup above)

2. Open the project in VS Code and install the "Dev Containers" extension

3. Use Command Palette (Ctrl+Shift+P) and select "Dev Containers: Reopen in Container"

The dev container will:
- Build a development environment with all dependencies
- Start MariaDB and phpMyAdmin services
- Mount your source code for live editing
- Run on port 8100 (to avoid conflicts with regular development)
- phpMyAdmin available on port 6002

### Production Setup

1. **Copy the example environment file:**

   ```bash
   cp .prod.env.example .prod.env
   ```

2. **Edit `.prod.env` with your production values:**

   ```bash
   # .prod.env (this file should be created on the production server)
   MYSQL_ROOT_PASSWORD=very_secure_root_password
   MYSQL_DATABASE=find_artek_django
   MYSQL_USER=find_artek_user  
   MYSQL_PASSWORD=very_secure_db_password
   SECRET_KEY=very_long_django_secret_key_50_chars_minimum
   DEBUG=False
   ENABLE_CRON=true
   THUMBNAIL_HEIGHT=400
   NETWORK_DRIVE_HOST=ait-pdfs
   NETWORK_DRIVE_SHARE=Qdrev/SUS/Groups/Arctic_web-data/SUS-PArcWeb01
   NETWORK_DRIVE_USER=SUS-Usr-Arctic-web@win.dtu.dk
   NETWORK_DRIVE_PASSWORD=your_network_drive_password
   ```

3. **Start production environment:**

   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

## Git Security Configuration

Add to your `.gitignore`:
```gitignore
# Environment files (NEVER commit these)
.env
.dev.env
.prod.env
*.env
!*.env.example
```

## Environment Variables Reference

### Required for All Environments
- `MYSQL_DATABASE` - Database name
- `MYSQL_USER` - Database user  
- `MYSQL_PASSWORD` - Database password
- `MYSQL_ROOT_PASSWORD` - Database root password
- `SECRET_KEY` - Django secret key (50+ random characters)

### Production-Specific (CIFS Network Drive)
- `NETWORK_DRIVE_HOST` - Network drive hostname (e.g., ait-pdfs)
- `NETWORK_DRIVE_SHARE` - Share path (e.g., Qdrev/SUS/Groups/Arctic_web-data/SUS-PArcWeb01)
- `NETWORK_DRIVE_USER` - Username for network drive access
- `NETWORK_DRIVE_PASSWORD` - Password for network drive

### Optional
- `ENABLE_CRON` - Enable/disable cron jobs (default: true for prod, false for dev)
- `THUMBNAIL_HEIGHT` - Height for generated thumbnails (default: 400)
- `DEBUG` - Django debug mode (should be False in production)

## Security Best Practices

1. **Never commit .env files to git** - Keep production secrets out of version control
2. **Create .prod.env directly on the production server** - Don't include it in deployments
3. **Use strong passwords (20+ characters)** - Generate secure credentials
4. **Use different passwords for each environment** - Dev and prod should have separate credentials  
5. **Rotate passwords regularly** - Change credentials periodically
6. **Limit access to production .env files** - Set proper file permissions (chmod 600 on Linux)
7. **Secure the production server** - Restrict access to deployment directories

## Deployment Automation

For automated deployments, consider using:
- **Ansible Vault** for encrypted variable storage
- **HashiCorp Vault** for secret management
- **AWS Secrets Manager / Azure Key Vault** for cloud deployments
- **CI/CD environment variables** (GitLab CI, GitHub Actions) with masked variables
