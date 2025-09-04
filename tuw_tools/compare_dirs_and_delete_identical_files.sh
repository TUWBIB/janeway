#!/bin/bash

# chatgpt
# ...
# logic reversed manually

# Usage message
usage() {
    echo "Usage: $0 [--exceute <source_dir> <target_dir>"
    echo
    echo "Finds files that exist in both directories with identical relative paths and content,"
    echo "then deletes them from the target directory."
    echo
    echo "Options:"
    echo "  --execute     Actually delete duplicate files."
    exit 1
}

# --- Parse arguments ---
EXCEUTE=0

# Extract dry-run flag and positional args
while [[ "$1" == --* ]]; do
    case "$1" in
        --execute)
            EXECUTE=1
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Get source and target directories
SOURCE_DIR="$1"
TARGET_DIR="$2"

# Check for missing arguments
if [[ -z "$SOURCE_DIR" || -z "$TARGET_DIR" ]]; then
    echo "Error: Source and target directories must be provided."
    usage
fi

# Check directories exist
if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Error: Source directory '$SOURCE_DIR' does not exist."
    exit 1
fi

if [[ ! -d "$TARGET_DIR" ]]; then
    echo "Error: Target directory '$TARGET_DIR' does not exist."
    exit 1
fi

echo "Comparing files from:"
echo "  Source: $SOURCE_DIR"
echo "  Target: $TARGET_DIR"
[[ $EXECUTE -ne 1 ]] && echo "Running in DRY-RUN mode..."

# --- Main logic ---
find "$SOURCE_DIR" -type f | while read -r file1; do
    # Compute relative path
    rel_path="${file1#$SOURCE_DIR/}"
    file2="$TARGET_DIR/$rel_path"

    # Check if file exists in target
    if [[ -f "$file2" ]]; then
        if cmp -s "$file1" "$file2"; then
            if [[ $EXECUTE -eq 1 ]]; then
                echo "Deleting: $file2"
                rm "$file2"
            else
                echo "[DRY-RUN] Would delete: $file2"
            fi
        fi
    fi
done
