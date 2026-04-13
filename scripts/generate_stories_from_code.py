import os
import re
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
EPICS_FILE = PROJECT_ROOT / "_bmad-output" / "planning-artifacts" / "epics.md"
SPRINT_STATUS_FILE = PROJECT_ROOT / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml"
OUT_DIR = PROJECT_ROOT / "_bmad-output" / "implementation-artifacts"

# Heuristics for basic file finding
DOMAIN_KEYWORDS = {
    "auth": ["auth", "user", "login", "register", "oauth", "password", "jwt"],
    "database": ["db", "prisma", "migrations", "schema", "seed"],
    "infra": ["docker", "nginx", "redis", "celery", "worker"],
    "document": ["document", "upload", "parse", "file", "storage"],
    "vector": ["vector", "embed", "chroma", "pinecone", "pgvector"],
    "chat": ["chat", "message", "conversation", "llm", "rag", "stream"],
    "sync": ["sync", "rocicorp", "zero", "local"],
    "billing": ["billing", "stripe", "subscription", "price", "webhook", "checkout"],
    "usage": ["usage", "quota", "limit", "token"],
}

def load_sprint_status():
    if not SPRINT_STATUS_FILE.exists():
        return {}
    with open(SPRINT_STATUS_FILE, "r") as f:
        data = yaml.safe_load(f)
    if not data or "development_status" not in data:
        return {}
    
    return data.get("development_status", {})

def find_related_files(keywords):
    related = []
    # simplistic scan of app and web
    search_dirs = [PROJECT_ROOT / "surfsense_backend" / "app", PROJECT_ROOT / "surfsense_web" / "src"]
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        for root, dirs, files in os.walk(sdir):
            for file in files:
                if file.endswith((".py", ".ts", ".tsx", ".js")):
                    path_str = os.path.join(root, file).lower()
                    if any(kw in path_str for kw in keywords):
                        rel = os.path.relpath(os.path.join(root, file), PROJECT_ROOT)
                        related.append(rel)
    return list(set(related))[:8] # Max 8 files to prevent giant lists

def parse_epics():
    if not EPICS_FILE.exists():
        print("epics.md not found!")
        return []
        
    with open(EPICS_FILE, "r") as f:
        content = f.read()

    stories = []
    current_epic_id = None
    
    epic_pattern = re.compile(r'^### Epic (\d+):', re.MULTILINE)
    story_pattern = re.compile(r'^#### Story ((\d+)\.(\d+)): (.+)', re.MULTILINE)
    
    lines = content.split('\n')
    current_story = None
    
    for line in lines:
        e_match = epic_pattern.match(line)
        if e_match:
            current_epic_id = e_match.group(1)
            continue
            
        s_match = story_pattern.match(line)
        if s_match:
            if current_story:
                stories.append(current_story)
            story_id = s_match.group(1)
            story_name = s_match.group(4).strip()
            current_story = {
                "id": story_id,
                "name": story_name,
                "desc_lines": []
            }
            continue
            
        if current_story and line.strip() and not line.startswith('#'):
            current_story["desc_lines"].append(line)

    if current_story:
        stories.append(current_story)
        
    return stories

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    status_map = load_sprint_status()
    stories = parse_epics()
    
    for s in stories:
        sid = s["id"]
        sname = s["name"]
        
        status = "backlog/ready-for-dev"
        sanitized_id = sid.replace('.', '-')
        for k, v in status_map.items():
            if k.startswith(sanitized_id + "-") or k == sanitized_id:
                status = v
                break
                
        filename = f"{sanitized_id}-{slugify(sname)}.md"
        
        # Determine keywords
        title_words = sname.lower().split()
        matched_keywords = set()
        for dom, kws in DOMAIN_KEYWORDS.items():
            if any(w in title_words for w in kws) or any(w in " ".join(s["desc_lines"]).lower() for w in kws):
                matched_keywords.update(kws)
                
        if not matched_keywords:
            matched_keywords = ["main", "app", "index"]
            
        related_files = find_related_files(matched_keywords)
        
        # Build Markdown
        md = f"# Story {sid}: {sname}\n\n"
        md += f"**Status:** {status}\n\n"
        md += "## PRD Requirements\n"
        md += "\n".join(s["desc_lines"]) + "\n\n"
        
        md += "## Architecture Compliance & As-Built Context\n"
        md += "> *This section is automatically generated to map implemented components to this story's requirements.*\n\n"
        if status == "done":
            md += "This story has been successfully implemented in the brownfield codebase. The following key files contain the core logic for this feature:\n\n"
        else:
            md += "This story is currently in the backlog. Implementation should likely integrate with or modify the following files:\n\n"
            
        if related_files:
            for f in related_files:
                md += f"- `{f}`\n"
        else:
            md += "- *No explicit file references found, general application domain applies.*\n"
            
        md += "\n"
        md += "## Implementation Notes\n"
        md += "- **UI/UX**: Needs to follow `surfsense_web` React/Tailwind standards.\n"
        md += "- **Backend**: Needs to follow `surfsense_backend` FastAPI standards.\n"
        
        out_path = OUT_DIR / filename
        with open(out_path, "w") as out:
            out.write(md)
            
        print(f"Generated {filename}")

if __name__ == "__main__":
    main()
