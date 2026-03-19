import os
import re

def process_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return # Skip binary or unreadable

    original_content = content
    
    def replacer(match):
        text = match.group(0)
        start = match.start()
        end = match.end()
        
        context_before = content[max(0, start-30):start]
        context_after = content[end:min(len(content), end+30)]
        
        # Exclusions based on User requirements:
        
        # 1. Environment variables (SURFSENSE_*)
        if "SURFSENSE_" in text.upper() + context_after.upper():
            return text
            
        # 2. Database tables, column names, python packges, and directories (surfsense_*)
        if text.lower() + context_after[:1] == "surfsense_":
            return text
            
        # 3. Internal API route paths
        if "/api/surfsense" in context_before.lower() + text.lower():
            return text
        if "/surfsense-docs" in context_before.lower() + text.lower():
            return text
            
        # 4. Celery Queue
        if "QUEUE=" in context_before.upper() or "queue=" in context_before.lower():
            return text
        if "queues=" in context_before.lower() or "queues=" in context_before.upper():
            return text
            
        # 5. DB connection strings and defaults
        if "DB_USER:-" in context_before or "DB_PASSWORD:-" in context_before or "DB_NAME:-" in context_before:
            return text
        if "5432/" in context_before or "DB_USER=" in context_before or "DB_PASSWORD=" in context_before or "DB_NAME=" in context_before:
            return text
            
        # 6. Legacy migration scripts old volumes
        full_after_lower = text.lower() + context_after.lower()
        if full_after_lower.startswith("surfsense-data") or full_after_lower.startswith("surfsense-pg14"):
            return text

        # If it passed exceptions, replace appropriately
        if text == "SurfSense":
            return "NeoNote"
        elif text == "surfsense":
            return "neonote"
        elif text == "SURFSENSE":
            return "NEONOTE"
        else:
            if text.istitle(): return "Neonote"
            elif text.islower(): return "neonote"
            elif text.isupper(): return "NEONOTE"
            return "NeoNote"

    new_content = re.sub(r'(?i)surfsense', replacer, content)
    
    # Taglines and Team
    new_content = new_content.replace("OSS Alternative to NotebookLM for Teams", "AI Research Hub for Teams")
    new_content = new_content.replace("OSS alternative to NotebookLM for Teams", "AI Research Hub for Teams")
    new_content = new_content.replace("SurfSense Team", "NeoNote")
    new_content = new_content.replace("surfsense team", "neonote")
    
    if new_content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {file_path}")

def main():
    exclude_dirs = {'.git', 'node_modules', '.next', 'dist', 'build', '__pycache__', '.venv', 'venv', '.cursor', 'docker/postgres_data', 'docker/redis_data'}
    
    base_dir = r"c:\Users\batoman\Documents\GitHub\Surfcode\neonote\neonote"
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if not any(d.endswith(ex) for ex in exclude_dirs) and d not in exclude_dirs]
        
        for file in files:
            if file in ["replace_surfsense.py", "find_surfsense.py", "search_results.txt", "task.md", "implementation_plan.md"]:
                continue
            process_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
