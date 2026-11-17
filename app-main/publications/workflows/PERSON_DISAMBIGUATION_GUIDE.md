# Person Disambiguation System

## Overview

The Person Disambiguation system is designed to match person names to existing database records in a consistent and reliable way. It addresses the challenges of matching names with character variants, different formats, and special identifiers.

## Key Components

### NameNormalizer

The `NameNormalizer` class provides consistent text normalization across the application:

- Handles Danish character substitutions (æ → ae, ø → oe, å → aa)
- Supports character substitutions for other languages (German, French, Spanish)
- Removes accents and normalizes case
- Generates relaxed name components for matching

### PersonMatcher

The `PersonMatcher` class provides a centralized API for person name matching:

- Supports multiple matching strategies with confidence scores
- Handles exact matches, relaxed matches, and specialized identifiers
- Prioritizes high-confidence matches and removes duplicates
- Provides simple methods for finding the best match or checking if a name likely refers to a new person

### Management Command: update_relaxed_names

The `update_relaxed_names` management command calculates and updates the `first_relaxed` and `last_relaxed` fields for all Person records:

- Uses the new `NameNormalizer` class for consistent name normalization
- Supports batch processing for large datasets
- Provides dry-run option to preview changes
- Shows progress and summary statistics

## Usage Examples

### Updating Person Records

```bash
# Update all Person records
python manage.py update_relaxed_names

# Preview changes without modifying the database
python manage.py update_relaxed_names --dry-run

# Process in larger batches for performance
python manage.py update_relaxed_names --batch-size 500
```

### Using the PersonMatcher in Code

```python
from publications.workflows.person_disambiguation import PersonMatcher

# Create a matcher
matcher = PersonMatcher()

# Find all potential matches
matches = matcher.find_matches("John Smith")
for match in matches:
    print(f"Match: {match['person'].name} (Confidence: {match['confidence']}, Type: {match['match_type']})")

# Get the best match only
best_match = matcher.get_best_match("John Smith")
if best_match:
    print(f"Best match: {best_match['person'].name}")
else:
    print("No matches found")

# Check if a name likely refers to a new person
if matcher.is_new_person("Unknown Person"):
    print("This is likely a new person")
```

### Manually Normalizing Names

```python
from publications.workflows.person_disambiguation import NameNormalizer

# Normalize a name
normalized = NameNormalizer.normalize_name("Jørgen Ægir")
print(normalized)  # "joergen aegir"

# Get relaxed name components
components = NameNormalizer.get_relaxed_name_components("María-José García López")
print(components)  # {'first_relaxed': 'm', 'last_relaxed': 'lopez'}
```

## Matching Strategies

The PersonMatcher uses several matching strategies with different confidence levels:

1. **Specialized Matches** (Highest Confidence):
   - Email matching
   - ID number matching (student and employee IDs)

2. **Exact Matches** (High Confidence):
   - Exact name matching
   - Company-assigned initials (e.g., 2-4 letter codes like "JDK")

3. **Relaxed Matches** (Medium Confidence):
   - Character variant normalization (using first_relaxed/last_relaxed fields)
   - Initial matching (first letter of first name + full last name)

Each match includes a confidence score indicating how reliable the match is considered to be.

## Comparison with Previous System

The new system improves on the previous approach in several ways:

- **Consistent Text Normalization**: Uses a dedicated class to ensure consistent handling of special characters
- **Structured Matching Logic**: Organizes matching strategies in a clear, maintainable way
- **Confidence Scoring**: Provides confidence scores to distinguish between different types of matches
- **Specialized Identifier Detection**: Better handling of emails, ID numbers, and company initials
- **Management Command**: Easy bulk updating of relaxed name fields

## Implementation Notes

This implementation runs in parallel with the existing system to allow for comparison and testing before full adoption. Once validated, the old implementation can be deprecated.
