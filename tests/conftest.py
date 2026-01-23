"""
Pytest configuration and fixtures for MatchForge tests.
"""
import json
import os
import pytest
from pathlib import Path


@pytest.fixture
def demo_jobs():
    """Load demo jobs dataset."""
    demo_path = Path(__file__).parent.parent / "data" / "demo_jobs.json"
    with open(demo_path, "r") as f:
        return json.load(f)


@pytest.fixture
def sample_resume_text():
    """Sample resume text for testing."""
    return """
John Smith
john.smith@email.com
555-123-4567
San Francisco, CA

PROFESSIONAL SUMMARY
Experienced DevOps Engineer with 6 years of experience in cloud infrastructure,
CI/CD pipelines, and container orchestration.

WORK EXPERIENCE

Senior DevOps Engineer | TechCorp Inc | 2021 - Present
- Designed and implemented Kubernetes clusters serving 10M daily requests
- Built CI/CD pipelines using Jenkins and GitHub Actions
- Managed AWS infrastructure using Terraform and CloudFormation
- Reduced deployment time by 70% through automation

DevOps Engineer | StartupXYZ | 2018 - 2021
- Implemented Docker containerization for microservices
- Set up monitoring using Prometheus and Grafana
- Automated infrastructure provisioning with Ansible

EDUCATION

Bachelor of Science in Computer Science
University of California, Berkeley | 2018

SKILLS
AWS, Kubernetes, Docker, Terraform, Jenkins, GitHub Actions,
Python, Bash, Prometheus, Grafana, CI/CD, Ansible, Linux
"""


@pytest.fixture
def sample_job_description():
    """Sample job description for testing."""
    return """
DevOps Engineer
StartupXYZ - Austin, TX (Remote)

We are seeking an experienced DevOps Engineer to join our growing team.

Required Skills:
- CI/CD pipelines (Jenkins, GitHub Actions)
- Container orchestration (Kubernetes, Docker)
- Cloud infrastructure (AWS preferred)
- Infrastructure as Code (Terraform)
- Scripting (Python, Bash)

Preferred Skills:
- ArgoCD or similar GitOps tools
- Prometheus and Grafana
- Go programming

Experience: 3-7 years

Salary: $125,000 - $155,000
"""


@pytest.fixture
def sample_user_profile():
    """Sample user profile for job matching."""
    return {
        "target_title": "DevOps Engineer",
        "skills": ["AWS", "Kubernetes", "Docker", "Terraform", "Jenkins", "Python"],
        "years_experience": 6,
        "salary_min": 120000,
        "salary_max": 160000,
        "locations": ["Remote", "Austin, TX", "San Francisco, CA"],
        "open_to_remote": True,
    }


@pytest.fixture
def poor_ats_resume():
    """Resume with multiple ATS issues for testing."""
    return """
★ CREATIVE RESUME ★

My Journey → From Student to Tech Leader

What I Bring:
→ 5 years building amazing things
→ Python, AWS, and more!

Contact me at:
john@example.com

About Me:
I'm passionate about technology and love solving problems.
"""


@pytest.fixture
def legacy_ats_resume():
    """Resume formatted for legacy ATS systems."""
    return """
JOHN SMITH
john.smith@email.com | 555-123-4567 | San Francisco, CA

WORK EXPERIENCE

Senior Software Engineer, TechCorp Inc, January 2021 - Present
- Developed REST APIs using Python and FastAPI
- Managed PostgreSQL databases with 99.9% uptime
- Led team of 5 engineers

Software Engineer, StartupXYZ, June 2018 - December 2020
- Built microservices using Node.js
- Implemented CI/CD pipelines with Jenkins
- Wrote unit and integration tests

EDUCATION

Bachelor of Science, Computer Science
University of California, Berkeley, May 2018

SKILLS
Python, JavaScript, PostgreSQL, AWS, Docker, Kubernetes, CI/CD, REST APIs
"""
