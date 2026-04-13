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
    return data.get("development_status", {})

def find_related_files(keywords):
    related = []
    search_dirs = [PROJECT_ROOT / "surfsense_backend" / "app", PROJECT_ROOT / "surfsense_web" / "src", PROJECT_ROOT / "surfsense_web" / "components", PROJECT_ROOT / "surfsense_web" / "app"]
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
    return list(set(related))[:8]

def parse_epics():
    if not EPICS_FILE.exists():
        return []
    with open(EPICS_FILE, "r") as f:
        content = f.read()

    stories = []
    epic_pattern = re.compile(r'^### Epic (\d+):', re.MULTILINE)
    story_pattern = re.compile(r'^#### Story ((\d+)\.(\d+)): (.+)', re.MULTILINE)
    lines = content.split('\n')
    current_story = None

    for line in lines:
        e_match = epic_pattern.match(line)
        if e_match:
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

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    status_map = load_sprint_status()
    stories = parse_epics()

    existing_manual_stories = ["3.5", "5.1", "5.2", "5.3", "5.4"]

    for s in stories:
        sid = s["id"]
        sname = s["name"]
        
        status = "backlog/ready-for-dev"
        sanitized_id = sid.replace('.', '-')
        key_found = None
        for k, v in status_map.items():
            if k.startswith(sanitized_id + "-") or k == sanitized_id:
                status = v
                key_found = k
                break
                
        if not key_found:
            continue
            
        filename = f"{key_found}.md"
        
        # We don't overwrite the manually generated ones except to rename them if needed!
        # Actually, let's just generate all of them to be clean, BUT wait, user said "ngoài stories 3.5 và epic 5".
        # So we skip fully overriding 3.5 and epic 5, but we MIGHT need to rename them.
        
        # Read old file if exists (using the messy name) to preserve content if we are skipping overriding
        # Wait, instead of doing that in python, I'll let python just generate new ones for the "other" stories,
        # and I will rename 3.5 and Epic 5 manually.

        if sid in existing_manual_stories:
            continue

        title_words = sname.lower().split()
        matched_keywords = set()
        for dom, kws in DOMAIN_KEYWORDS.items():
            if any(w in title_words for w in kws) or any(w in " ".join(s["desc_lines"]).lower() for w in kws):
                matched_keywords.update(kws)

        if not matched_keywords:
            matched_keywords = ["main", "app", "index"]

        related_files = find_related_files(matched_keywords)

        desc_text = "\n".join(s["desc_lines"])
        md = f"""# Story {sid}: {sname}

**Status:** {status}
**Epic:** Epic {sid.split('.')[0]}
**Story Key:** `{key_found}`

## 📖 Story Requirements (Context & PRD)
> This section maps directly to the original Product Requirements Document and Epics definition.

{desc_text}

## 🏗️ Architecture & Technical Guardrails
> Critical instructions for the development agent based on the project's established architecture.

### Technical Requirements
- Language/Framework: React, Next.js (TypeScript) for Web; FastAPI (Python) for Backend.
- Database: Prisma/Supabase.
- Strict Type checking must be enforced. No `any` types.

### Code Organization
This story is currently marked as `{status}`. Implementation should target the following components/files:

"""
        if related_files:
            for f in related_files:
                md += f"- `{f}`\n"
        else:
            md += "- *Standard application patterns apply. Use `Serena` to locate exact files.*\n"

        md += """
### Developer Agent Constraints
1. **No Destructive Refactors**: Extend existing modules when possible.
2. **Context Check**: Always refer back to `task.md` and use Context7 to verify latest SDK usages.
3. **BMad Standard**: Update the sprint status using standard metrics.

## 🧪 Testing & Validation Requirements
- All new endpoints must be tested.
- Frontend components should gracefully degrade.
- Do not introduce regressions into existing user workflows.

## 📈 Completion Status
*(To be updated by the agent when completing this story)*
- Start Date: _____________
- Completion Date: _____________
- Key Files Changed:
  - 

"""
        out_path = OUT_DIR / filename
        with open(out_path, "w") as out:
            out.write(md)

        print(f"Generated {filename}")

if __name__ == "__main__":
    main()
