import os
import yaml
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class SkillMetadata(BaseModel):
    name: str
    description: str
    always: bool = False
    emoji: Optional[str] = None
    homepage: Optional[str] = None
    skillKey: Optional[str] = None
    primaryEnv: Optional[str] = None
    os: List[str] = []
    requires: Dict[str, Any] = {}
    install: List[Dict[str, Any]] = []

class SkillEntry(BaseModel):
    name: str
    description: str
    source: str
    bundled: bool
    filePath: str
    baseDir: str
    metadata: Optional[SkillMetadata] = None
    body: str = ""
    commands: List[str] = []

class SkillMdParser:
    """
    Parses SKILL.md files to extract metadata, description, and instructions.
    """
    @staticmethod
    def parse_file(file_path: Path) -> Optional[SkillEntry]:
        if not file_path.exists():
            return None
            
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Extract frontmatter
            frontmatter = {}
            body = content
            
            if content.startswith("---"):
                parts = re.split(r"^---\s*$", content, maxsplit=2, flags=re.MULTILINE)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                        body = parts[2]
                    except yaml.YAMLError:
                        pass
            
            # Extract basic info
            name = frontmatter.get("name")
            description = frontmatter.get("description", "")
            
            # Fallback if name/description not in frontmatter
            if not name:
                # Try to find first H1
                h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
                if h1_match:
                    name = h1_match.group(1).strip()
                else:
                    name = file_path.parent.name
            
            if not description:
                # Try to find first paragraph after H1
                lines = body.split("\n")
                for i, line in enumerate(lines):
                    if line.startswith("# "):
                        # Look for next non-empty line
                        for next_line in lines[i+1:]:
                            if next_line.strip():
                                description = next_line.strip()
                                break
                        break
            
            # Extract bash commands from code blocks
            commands = re.findall(r"```bash\n(.*?)\n```", body, re.DOTALL)
            
            # Map frontmatter to SkillMetadata
            autocrab = frontmatter.get("autocrab", {})
            metadata = SkillMetadata(
                name=name,
                description=description,
                always=autocrab.get("always", False),
                emoji=autocrab.get("emoji"),
                homepage=autocrab.get("homepage"),
                skillKey=autocrab.get("skillKey"),
                primaryEnv=autocrab.get("primaryEnv"),
                os=autocrab.get("os", []),
                requires=autocrab.get("requires", {}),
                install=autocrab.get("install", [])
            )
            
            return SkillEntry(
                name=name,
                description=description,
                source="autocrab-skill",
                bundled=False,
                filePath=str(file_path),
                baseDir=str(file_path.parent),
                metadata=metadata,
                body=body,
                commands=commands
            )
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None

def load_skills_from_dir(directory: Path) -> List[SkillEntry]:
    """
    Scans directory for skills (folders with SKILL.md).
    """
    skills = []
    if not directory.exists():
        return skills
        
    for item in directory.iterdir():
        if item.is_dir():
            skill_md = item / "SKILL.md"
            if skill_md.exists():
                entry = SkillMdParser.parse_file(skill_md)
                if entry:
                    skills.append(entry)
                    
    return skills
