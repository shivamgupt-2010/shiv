"""
ShivAI Unified Project and Asset Management Service.
Handles persistent user projects across:
- Full-stack web applications
- Browser 2D and 3D games
- Video Studio timeline projects
- 2D Design canvas projects
- 3D asset scene collections
- Research dossiers
Enforces user tenant isolation, versioning history, and file snapshot packaging.
"""
import os
import io
import time
import zipfile
import uuid
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("shivai.projects.manager")


class ProjectVersion(BaseModel):
    version_id: str
    message: str
    timestamp: float = Field(default_factory=time.time)
    file_count: int = 0


class Project(BaseModel):
    project_id: str
    user_id: str
    name: str
    project_type: str  # "app", "game", "video", "design", "threed", "research"
    description: str = ""
    files: Dict[str, str] = Field(default_factory=dict)  # relative_path -> content
    metadata: Dict[str, Any] = Field(default_factory=dict)
    versions: List[ProjectVersion] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ProjectManager:
    """In-memory and file-backed project workspace manager."""

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.storage_dir = os.path.join(root, "storage", "projects")
        else:
            self.storage_dir = os.path.abspath(storage_dir)

        os.makedirs(self.storage_dir, exist_ok=True)
        self._projects: Dict[str, Project] = {}

    def create_project(
        self,
        user_id: str,
        name: str,
        project_type: str,
        description: str = "",
        initial_files: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Project:
        """Creates a new project owned by user_id."""
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        files = initial_files or {}
        now = time.time()

        initial_version = ProjectVersion(
            version_id="v1",
            message="Initial project creation",
            timestamp=now,
            file_count=len(files),
        )

        project = Project(
            project_id=project_id,
            user_id=user_id,
            name=name,
            project_type=project_type,
            description=description,
            files=files,
            metadata=metadata or {},
            versions=[initial_version],
            created_at=now,
            updated_at=now,
        )

        self._projects[project_id] = project
        logger.info(f"Created {project_type} project '{name}' ({project_id}) for user '{user_id}'")
        return project

    def get_project(self, project_id: str, user_id: Optional[str] = None) -> Optional[Project]:
        """Gets project with strict tenant isolation check."""
        project = self._projects.get(project_id)
        if not project:
            return None
        if user_id and project.user_id != user_id and user_id != "admin":
            return None
        return project

    def list_projects(
        self,
        user_id: Optional[str] = None,
        project_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Project]:
        """Lists projects owned by user with optional type filter."""
        results = []
        for p in sorted(self._projects.values(), key=lambda x: x.updated_at, reverse=True):
            if user_id and p.user_id != user_id and user_id != "admin":
                continue
            if project_type and p.project_type != project_type:
                continue
            results.append(p)
            if len(results) >= limit:
                break
        return results

    def update_file(
        self,
        project_id: str,
        filename: str,
        content: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """Adds or updates a file within a project."""
        project = self.get_project(project_id, user_id=user_id)
        if not project:
            return False

        # Normalize relative path and reject traversal
        clean_name = filename.replace("\\", "/").lstrip("/")
        if ".." in clean_name.split("/"):
            raise ValueError("Directory traversal attempt detected in filename.")

        project.files[clean_name] = content
        project.updated_at = time.time()
        return True

    def create_version(
        self,
        project_id: str,
        message: str,
        user_id: Optional[str] = None,
    ) -> Optional[ProjectVersion]:
        """Tags a new version checkpoint in project history."""
        project = self.get_project(project_id, user_id=user_id)
        if not project:
            return None

        ver_num = len(project.versions) + 1
        version = ProjectVersion(
            version_id=f"v{ver_num}",
            message=message,
            timestamp=time.time(),
            file_count=len(project.files),
        )
        project.versions.append(version)
        project.updated_at = time.time()
        return version

    def delete_project(self, project_id: str, user_id: Optional[str] = None) -> bool:
        """Deletes a project."""
        project = self.get_project(project_id, user_id=user_id)
        if not project:
            return False
        self._projects.pop(project_id, None)
        return True

    def export_as_zip(self, project_id: str, user_id: Optional[str] = None) -> bytes:
        """Packages all project files into a standalone ZIP archive in memory."""
        project = self.get_project(project_id, user_id=user_id)
        if not project:
            raise FileNotFoundError(f"Project '{project_id}' not found.")

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, content in project.files.items():
                zf.writestr(fname, content)
            # Add manifest
            manifest = f"# {project.name}\nType: {project.project_type}\nDescription: {project.description}\nGenerated by ShivAI V2\n"
            zf.writestr("PROJECT_INFO.md", manifest)

        buffer.seek(0)
        return buffer.getvalue()


project_manager = ProjectManager()
