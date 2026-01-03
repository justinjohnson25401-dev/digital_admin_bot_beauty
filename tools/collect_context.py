
import os
import glob

# Paths to search for files
search_paths = [
    '.docs/**/*.md',
    'handlers/booking.py',
    'handlers/booking/',
    'utils/db/',
    'admin_bot/handlers/staff/',
    'configs/client_lite.json',
    'main.py',
    'admin_bot/main.py'
]

# Paths to ignore
ignore_paths = [
    '.docs/archive/',
    '__pycache__',
    '.git'
]

# File extensions to ignore
ignore_extensions = ['.jpg', '.png']

# Output file
output_file = 'FULL_CONTEXT.txt'

def should_ignore(path):
    """Check if a path should be ignored."""
    for ignore_path in ignore_paths:
        if ignore_path in path:
            return True
    for ignore_extension in ignore_extensions:
        if path.endswith(ignore_extension):
            return True
    return False

def collect_context():
    """Collects context from specified files and directories."""
    all_files = set()

    for path in search_paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    full_path = os.path.join(root, file)
                    if not should_ignore(full_path):
                        all_files.add(full_path)
        elif os.path.isfile(path):
            if not should_ignore(path):
                all_files.add(path)
        else: # Handle glob patterns
            for file_path in glob.glob(path, recursive=True):
                 if not should_ignore(file_path) and os.path.isfile(file_path):
                    all_files.add(file_path)


    with open(output_file, 'w', encoding='utf-8') as outfile:
        for file_path in sorted(list(all_files)):
            try:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(f'\n=== FILE: {file_path} ===\n')
                    outfile.write(infile.read())
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")

    print("✅ Контекст собран в FULL_CONTEXT.txt")

if __name__ == "__main__":
    collect_context()
