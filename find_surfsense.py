import os
import re

def search_directory(directory="."):
    exclude_dirs = {'.git', 'node_modules', '.next', 'dist', 'build', '__pycache__', '.venv', 'venv', '.cursor', 'docker/postgres_data', 'docker/redis_data'}
    
    pattern = re.compile(r'(?i)surfsense')
    
    results = []
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not any(d.endswith(ex) for ex in exclude_dirs) and d not in exclude_dirs]
        
        for file in files:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            results.append(f"{file_path}:{line_num}: {line.strip()[:150]}")
            except Exception:
                pass # skip binary files or unreadable files
                
    with open('search_results.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))

if __name__ == "__main__":
    search_directory(r"c:\Users\batoman\Documents\GitHub\Surfcode\neonote\neonote")
    print("Search complete. Check search_results.txt")
