# Thumbnail Generation System

This system automatically generates thumbnails for PDF reports that don't have them.

## Components

1. **Django Management Command**: `generate_thumbnails.py`
2. **Cron Script**: `scripts/generate_thumbnails_cron.sh` (in the image: `/usr/local/bin/generate_thumbnails_cron.sh`)
3. **Cron job file**: `docker/cron/find_artek_thumbnails` (in the image: `/etc/cron.d/find_artek_thumbnails`)
4. **Dependencies**: `pdf2image` and `poppler-utils`

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

The image contains a nightly cron job, set up the same way as in monitoring_db:

- The job file `/etc/cron.d/find_artek_thumbnails` (from `docker/cron/find_artek_thumbnails`,
  owner root, mode 0644) runs `/usr/local/bin/generate_thumbnails_cron.sh` at 02:00 container
  time (UTC unless `TZ` is set) as `dockeruser`.
- With `ENABLE_CRON=true`, the entrypoint (`scripts/docker-entrypoint.sh`) starts the cron
  daemon through `sudo`, then runs the container's command (gunicorn). The startup log says
  `Cron enabled: ...` or `Cron disabled ...`. With `ENABLE_CRON` unset or anything other than
  `true`, no cron daemon runs.
- `THUMBNAIL_HEIGHT` (default 400) sets the height. The job reads it, together with the DB
  settings and `SECRET_KEY`, from the container's environment: cron gives its jobs an almost
  empty environment, so the script loads the environment of PID 1 from `/proc/1/environ`
  (readable only by `dockeruser` and root; nothing from it is printed or written to disk).
- Output goes to the container log, each line prefixed with a timestamp and `[thumbnails]`:

```bash
docker logs webapp-find-artek 2>&1 | grep '\[thumbnails\]'
```

**Enable cron:**
```bash
# in the env file used by compose, or as environment of the service
ENABLE_CRON=true
THUMBNAIL_HEIGHT=400  # optional, defaults to 400
```

**Check it in a running container:**
```bash
docker logs webapp-find-artek 2>&1 | grep -m1 Cron     # startup line: enabled/disabled
docker exec webapp-find-artek sh -c 'for c in /proc/[0-9]*/comm; do read -r n < "$c" && [ "$n" = cron ] && echo "cron running"; done'
docker exec webapp-find-artek cat /etc/cron.d/find_artek_thumbnails
```

**Run the job now (as `dockeruser`, the default user of `docker exec`), output to the terminal:**
```bash
docker exec webapp-find-artek generate_thumbnails_cron.sh        # height from THUMBNAIL_HEIGHT
docker exec webapp-find-artek generate_thumbnails_cron.sh 600    # explicit height
```

The script refuses to run as root, so thumbnails on the share always belong to uid 30000.

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
- The job runs as `dockeruser` (UID 30000) to match file ownership
- Media files should be owned by `dockeruser:dockeruser` or have group write access

**Check permissions:**
```bash
# Inside container, check media directory permissions
ls -la /mnt/shared-project-data/media/reports/
```

### 2. Environment Variables
Cron jobs get a minimal environment. `generate_thumbnails_cron.sh` loads the container's
environment from `/proc/1/environ` when it runs without the image's environment (i.e. from
cron). Values arrive unchanged (the file is NUL-separated, no quoting involved).

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
- The job file is part of the image; the cron daemon is started by the entrypoint on every
  container start when `ENABLE_CRON=true`. Nothing has to be set up by hand.

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
- All output goes to the container log (`docker logs`), prefixed with `[thumbnails]`; docker's
  log rotation applies. There is no separate log file.
- The script exits non-zero on failure and logs `ERROR: thumbnail generation failed ...`.

```bash
docker logs webapp-find-artek 2>&1 | grep '\[thumbnails\].*ERROR'
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
# All runs
docker logs webapp-find-artek 2>&1 | grep '\[thumbnails\]'

# Runs of today
docker logs webapp-find-artek 2>&1 | grep "^$(date '+%Y-%m-%d') .*\[thumbnails\]"
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
