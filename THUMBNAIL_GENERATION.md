# Thumbnail Generation System

This system automatically generates thumbnails for PDF reports that don't have them.

## Components

1. **Django Management Command**: `generate_thumbnails.py`
2. **Cron Script**: `generate_thumbnails_cron.sh`
3. **Dependencies**: `pdf2image` and `poppler-utils`

## Manual Usage

### Run the management command directly:
```bash
# Generate thumbnails for all publications missing them
python manage.py generate_thumbnails

# Generate thumbnails with verbose output
python manage.py generate_thumbnails --verbose

# Generate thumbnails with custom height (e.g., 600px)
python manage.py generate_thumbnails --height 600

# Force regeneration of existing thumbnails
python manage.py generate_thumbnails --force

# Generate thumbnail for a specific publication
python manage.py generate_thumbnails --publication-id 123

# Dry run (see what would be done without doing it)
python manage.py generate_thumbnails --dry-run

# Combine options: custom height with force regeneration
python manage.py generate_thumbnails --height 300 --force --verbose
```

## Automated Setup (Cron)

### Option 1: Container-Internal Cron (Recommended)

The Docker containers now include built-in cron support. Enable it using environment variables:

**Enable cron in docker-compose:**
```yaml
# In your .env file or docker-compose.yml
ENABLE_CRON=true
THUMBNAIL_HEIGHT=400  # Optional, defaults to 400
```

**Or set environment variables when running:**
```bash
# Development
ENABLE_CRON=true docker-compose -f docker-compose.develop.yml up -d

# Production  
ENABLE_CRON=true docker-compose -f docker-compose.prod.yml up -d
```

**Manual setup inside running container:**
```bash
# Enter the container
docker exec -it <container_name> bash

# Set up cron (run as root)
/usr/local/bin/setup_cron.sh

# Verify cron job
crontab -u dockeruser -l

# Check cron service status
service cron status
```

### Option 2: Host-Based Cron

### Option 2: Host-Based Cron

For systems running the Docker container, add this to your host's crontab:

```bash
# Run every night at 2 AM with default height (400px)
0 2 * * * docker exec <container_name> /usr/local/bin/generate_thumbnails_cron.sh

# Run every night at 2 AM with custom height (600px)
0 2 * * * docker exec <container_name> /usr/local/bin/generate_thumbnails_cron.sh 600
```

### 3. Log monitoring

The script logs to `/var/log/find_artek/thumbnail-generation.log`. Monitor this file for:
- Success/failure of thumbnail generation
- Error details for problematic PDFs
- Processing statistics

## Thumbnail Specifications

- **Height**: 400 pixels by default (configurable with `--height` parameter)
- **Width**: Calculated to maintain original aspect ratio
- **Format**: JPEG
- **Quality**: 85% with optimization and progressive encoding
- **DPI**: 150 (good balance of quality and processing speed)
- **Size Range**: Height can be set between 50-2000 pixels

## File Locations

- **PDFs**: `/mnt/shared-project-data/media/reports/{year}/{number}.pdf`
- **Thumbnails**: `/mnt/shared-project-data/media/reports/{year}/thumbs/{number}_thumb.jpg`

## Configuration Options

### Thumbnail Height
You can specify custom thumbnail heights using the `--height` parameter:

- **Minimum**: 50 pixels
- **Maximum**: 2000 pixels  
- **Default**: 400 pixels
- **Aspect Ratio**: Always maintained automatically

**Examples:**
```bash
# Small thumbnails for mobile
python manage.py generate_thumbnails --height 200

# Large thumbnails for high-resolution displays
python manage.py generate_thumbnails --height 800

# Standard web thumbnails (default)
python manage.py generate_thumbnails --height 400
```

### Use Cases for Different Sizes
- **150-250px**: Mobile thumbnails, list views
- **300-400px**: Standard web display (default)
- **500-800px**: High-resolution displays, detailed previews
- **1000+px**: Print-quality thumbnails

## User Considerations for Cron

### 1. File Permissions
**Issue**: Cron jobs run with limited environment and may have permission issues.

**Solutions:**
- The script runs as `dockeruser` (UID 30000) to match file ownership
- Log directory `/var/log/find_artek/` is created with proper permissions
- Media files should be owned by `dockeruser:dockeruser` or have group write access

**Check permissions:**
```bash
# Inside container, check media directory permissions
ls -la /mnt/shared-project-data/media/reports/

# Fix permissions if needed (run as root)
chown -R dockeruser:dockeruser /mnt/shared-project-data/media/reports/
chmod -R 755 /mnt/shared-project-data/media/reports/
```

### 2. Environment Variables
**Issue**: Cron has a minimal environment and may not have Django settings.

**Solutions:**
- The script explicitly sets `PYTHONPATH` and changes to `/app` directory
- Django settings are loaded automatically from the project
- Database credentials are passed through Docker environment variables

### 3. Memory Considerations
**Issue**: Large PDFs or many simultaneous processes can cause memory issues.

**Solutions:**
- Script processes one publication at a time
- Uses single thread for PDF conversion (`thread_count=1`)
- Monitor container memory usage: `docker stats <container_name>`

**Memory monitoring:**
```bash
# Monitor memory usage during thumbnail generation
docker exec <container_name> top -p $(docker exec <container_name> pgrep -f generate_thumbnails)
```

### 4. Container Lifecycle
**Issue**: Cron jobs are lost when container restarts.

**Solutions:**
- Use `ENABLE_CRON=true` environment variable for automatic setup
- Cron is configured at container startup via entrypoint script
- Jobs persist across container restarts when using environment variables

### 5. Timezone Considerations
**Issue**: Cron jobs run in container timezone, which may differ from host.

**Solutions:**
```bash
# Check container timezone
docker exec <container_name> date

# Set timezone if needed (add to Dockerfile or docker-compose)
environment:
  TZ: Europe/Copenhagen  # or your preferred timezone
```

### 6. Logging and Monitoring
**Issue**: Cron job failures may go unnoticed.

**Solutions:**
- All output logged to `/var/log/find_artek/thumbnail-generation.log`
- Script includes success/failure exit codes
- Use log monitoring tools or alerts

**Log monitoring setup:**
```bash
# View live logs
docker exec -it <container_name> tail -f /var/log/find_artek/thumbnail-generation.log

# Check for errors
docker exec <container_name> grep -i error /var/log/find_artek/thumbnail-generation.log

# Set up log rotation (add to container)
echo '/var/log/find_artek/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}' > /etc/logrotate.d/find_artek
```

### 7. Database Connectivity
**Issue**: Cron jobs may run before database is ready.

**Solutions:**
- Django ORM handles connection retries automatically
- Script includes error handling for database issues
- Consider adding health checks to docker-compose

### 8. Security Considerations
**Issue**: Cron jobs run with elevated privileges.

**Solutions:**
- Jobs run as `dockeruser` (non-root)
- Script validates input parameters
- File operations restricted to designated directories
- No sensitive data in cron job definitions

## Troubleshooting

### Common Issues

1. **"pdf2image package is not installed"**
   - Solution: Install with `pip install pdf2image`
   - Make sure `poppler-utils` is installed on the system

2. **"PDF file not found"**
   - Check that the PDF file exists at the expected location
   - Verify file permissions

3. **"Permission denied" when creating thumbnails**
   - Check write permissions on the thumbnails directory
   - Ensure the thumbnails directory exists

4. **Out of memory errors**
   - The script processes one publication at a time to minimize memory usage
   - For very large PDFs, consider increasing available memory

### Debug Mode

Run with verbose output to see detailed processing information:
```bash
python manage.py generate_thumbnails --verbose --dry-run

# Test with custom height
python manage.py generate_thumbnails --verbose --dry-run --height 300
```

### Checking Logs

```bash
# View recent log entries
tail -f /var/log/find_artek/thumbnail-generation.log

# View logs from last run
grep "$(date '+%Y-%m-%d')" /var/log/find_artek/thumbnail-generation.log
```

## Performance Notes

- Processing time depends on PDF size and complexity
- Typical processing: 1-3 seconds per thumbnail
- Memory usage: ~50-100MB per PDF during processing
- Generated thumbnails are typically 20-50KB each

## Integration with Templates

The existing template system automatically uses generated thumbnails:
- If thumbnail exists: displays the generated thumbnail
- If thumbnail missing: shows "preview not available" image

No template changes are required - thumbnails are automatically detected via the existing `thumb_file` template tag.
