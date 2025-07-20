# PDF Filename Normalization Management Command

This document explains how to use the `normalize_pdf_filenames` Django management command that standardizes PDF filenames to match publication number format.

## Overview

The `normalize_pdf_filenames` command ensures that all PDF files in the publications system follow a consistent naming convention based on the publication number (e.g., `01-06.pdf`, `14-28.pdf`). This standardization is essential for:

- Reliable thumbnail generation using publication numbers
- Consistent URL patterns in templates
- Better file organization and identification

## Command Location

```
app-main/publications/management/commands/normalize_pdf_filenames.py
```

## Basic Usage

### Dry Run (Recommended First Step)

Always start with a dry run to see what changes would be made without actually modifying any files:

```bash
python manage.py normalize_pdf_filenames --dry-run
```

This will show you:
- Which files need to be renamed
- Any conflicts where target filenames already exist
- Total count of publications processed

### Execute the Normalization

Once you've reviewed the dry run results, execute the actual normalization:

```bash
python manage.py normalize_pdf_filenames
```

## Command Options

### `--dry-run`
Shows what would be renamed without making any changes.

```bash
python manage.py normalize_pdf_filenames --dry-run
```

### `--verbose`
Shows detailed output for each publication processed, including those already correctly named.

```bash
python manage.py normalize_pdf_filenames --verbose
```

### `--publication-id <ID>`
Process only a specific publication by its database ID.

```bash
python manage.py normalize_pdf_filenames --publication-id 123
```

### `--force`
Force processing even if target filename already exists (will overwrite existing files).

```bash
python manage.py normalize_pdf_filenames --force
```

**⚠️ Warning**: Use `--force` carefully as it will delete existing files with the same target name.

## Common Usage Patterns

### 1. Initial Assessment
```bash
# See what needs to be changed
python manage.py normalize_pdf_filenames --dry-run --verbose
```

### 2. Process All Files
```bash
# First, dry run to check
python manage.py normalize_pdf_filenames --dry-run

# Then execute
python manage.py normalize_pdf_filenames
```

### 3. Handle Conflicts
```bash
# If conflicts exist, review them first
python manage.py normalize_pdf_filenames --dry-run

# Force overwrite if safe to do so
python manage.py normalize_pdf_filenames --force
```

### 4. Process Single Publication
```bash
# Test with one publication first
python manage.py normalize_pdf_filenames --publication-id 123 --dry-run

# Then execute
python manage.py normalize_pdf_filenames --publication-id 123
```

## Understanding the Output

### Normal Renaming
```
Publication 45 (14-28): SfM_ArcticTech_s131393_s131594_FINAL_PDF.pdf -> 14-28.pdf
```

### Already Correct
When using `--verbose`, you'll see publications that are already correctly named:
```
Processing publication 12 (01-15)...
```

### Conflicts
```
Publication 51 (11-30): Target file already exists: 11-30.pdf (use --force to overwrite)
```

### Errors
```
Publication 123 (05-11): PDF file not found at /path/to/file.pdf
```

## Example Session

Here's a typical workflow:

```bash
# 1. Check what needs to be done
$ python manage.py normalize_pdf_filenames --dry-run
DRY RUN MODE: No files will be renamed or database updated
Processing 479 publications with PDF files
  Publication 6 (01-06): 01-06a.pdf -> 01-06.pdf
  Publication 45 (14-28): SfM_ArcticTech_s131393_s131594_FINAL_PDF.pdf -> 14-28.pdf
  Publication 51 (11-30): Target file already exists: 11-30.pdf (use --force to overwrite)
  Publication 376 (05-31): Target file already exists: 05-31.pdf (use --force to overwrite)
  Publication 84 (15-05): Properties of bricks produced from Greenlandic marine sediments.pdf -> 15-05.pdf
  Publication 110 (15-21): BuildingMaterialsFromLocalResources.pdf -> 15-21.pdf
  Publication 134 (15-31): SfM_Arch_Tech_Guarnati_Righetti.pdf -> 15-31.pdf
  Publication 93 (15-18): Use of Discarded Fishing Nets as Near Surface Mounted Reinforcement in Concrete Beams.pdf -> 15-18.pdf

==================================================
SUMMARY:
  Processed: 479
  Renamed: 6
  Already correct: 471
  Skipped: 2
  Errors: 0
==================================================

# 2. Execute the normalization
$ python manage.py normalize_pdf_filenames
Processing 479 publications with PDF files
  Publication 6 (01-06): 01-06a.pdf -> 01-06.pdf
  Publication 45 (14-28): SfM_ArcticTech_s131393_s131594_FINAL_PDF.pdf -> 14-28.pdf
  Publication 84 (15-05): Properties of bricks produced from Greenlandic marine sediments.pdf -> 15-05.pdf
  Publication 110 (15-21): BuildingMaterialsFromLocalResources.pdf -> 15-21.pdf
  Publication 134 (15-31): SfM_Arch_Tech_Guarnati_Righetti.pdf -> 15-31.pdf
  Publication 93 (15-18): Use of Discarded Fishing Nets as Near Surface Mounted Reinforcement in Concrete Beams.pdf -> 15-18.pdf

==================================================
SUMMARY:
  Processed: 479
  Renamed: 6
  Already correct: 471
  Skipped: 2
  Errors: 0
==================================================

# 3. Handle remaining conflicts individually
$ python manage.py normalize_pdf_filenames --publication-id 51 --force
Processing single publication ID: 51
  Publication 51 (11-30): 11-30_1.pdf -> 11-30.pdf

==================================================
SUMMARY:
  Processed: 1
  Renamed: 1
  Already correct: 0
  Skipped: 0
  Errors: 0
==================================================
```

## Safety Features

### Atomic Operations
All file operations are wrapped in database transactions, ensuring that if the file rename fails, the database won't be updated with the wrong filename.

### Conflict Detection
The command detects when target filenames already exist and requires explicit `--force` flag to overwrite.

### Comprehensive Logging
All operations are logged to Django's logging system for audit trails.

### Dry Run Mode
Always test changes with `--dry-run` before executing.

## Troubleshooting

### File Not Found Errors
If you see "PDF file not found" errors, check:
- The file path in the database is correct
- The `MEDIA_ROOT` setting is properly configured
- File permissions allow access

### Permission Errors
Ensure the Django process has write permissions to the media directory:
```bash
chmod -R 755 /path/to/media/publications/
```

### Database Errors
If database updates fail, check:
- Database connectivity
- File model field constraints
- Transaction isolation levels

## Related Commands

This command works well with the thumbnail generation system:

```bash
# Normalize filenames first
python manage.py normalize_pdf_filenames

# Then generate thumbnails
python manage.py generate_thumbnails
```

## Dependencies

- `pdf2image` package (for PDF validation)
- `poppler-utils` system package
- Django ORM with transaction support
- File system write permissions

## Notes

- The command only processes publications that have a file attached
- Filenames are normalized to the format `{publication.number}.pdf`
- Directory structure is preserved; only the filename is changed
- Database file references are updated to match the new filenames
