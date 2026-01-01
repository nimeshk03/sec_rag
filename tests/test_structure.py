import os
import sys
from pathlib import Path

def test_project_structure():
    base_dir = Path(__file__).parent.parent
    
    required_dirs = [
        "src",
        "src/api",
        "src/data",
        "src/embeddings",
        "src/retrieval",
        "src/safety",
        "tests",
        "scripts"
    ]
    
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        assert full_path.exists(), f"Directory {dir_path} does not exist"
        assert full_path.is_dir(), f"{dir_path} is not a directory"

def test_required_files():
    base_dir = Path(__file__).parent.parent
    
    required_files = [
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        ".env.example",
        ".dockerignore",
        "render.yaml",
        "README.md",
        "pytest.ini",
        "src/__init__.py",
        "src/api/__init__.py",
        "src/api/main.py",
        "tests/__init__.py"
    ]
    
    for file_path in required_files:
        full_path = base_dir / file_path
        assert full_path.exists(), f"File {file_path} does not exist"
        assert full_path.is_file(), f"{file_path} is not a file"

def test_requirements_content():
    base_dir = Path(__file__).parent.parent
    req_file = base_dir / "requirements.txt"
    
    content = req_file.read_text()
    
    required_packages = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "supabase",
        "groq",
        "sentence-transformers",
        "rank-bm25",
        "beautifulsoup4",
        "requests",
        "python-dotenv",
        "pytest"
    ]
    
    for package in required_packages:
        assert package in content, f"Package {package} not in requirements.txt"

def test_docker_files_exist():
    base_dir = Path(__file__).parent.parent
    
    dockerfile = base_dir / "Dockerfile"
    compose = base_dir / "docker-compose.yml"
    
    assert dockerfile.exists()
    assert compose.exists()
    
    dockerfile_content = dockerfile.read_text()
    assert "FROM python:3.11-slim" in dockerfile_content
    assert "EXPOSE 8000" in dockerfile_content
    
    compose_content = compose.read_text()
    assert "version:" in compose_content
    assert "8000:8000" in compose_content
