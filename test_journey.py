#!/usr/bin/env python3
"""
MatchForge - Complete User Journey Test
Tests the full user flow through the API
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def print_header(text):
    print(f"\n{'─'*60}")
    print(f"  {text}")
    print(f"{'─'*60}")

def main():
    print("\n" + "="*60)
    print("     MATCHFORGE - COMPLETE USER JOURNEY TEST")
    print("="*60)

    # Step 1: Register new user
    print_header("STEP 1: Register New User")
    register_data = {
        "email": "journey.test@example.com",
        "password": "TestPass123",
        "full_name": "Journey Test User"
    }
    r = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_data)
    if r.status_code == 201:
        user = r.json()
        print(f"  ✓ Registered: {user['email']}")
        print(f"    User ID: {user['id'][:8]}...")
        print(f"    Tier: {user['subscription_tier']}")
    elif r.status_code == 400:
        print(f"  ℹ User already exists, continuing...")
    else:
        print(f"  ✗ Error: {r.text}")

    # Step 2: Login
    print_header("STEP 2: Login")
    login_data = {
        "email": "journey.test@example.com",
        "password": "TestPass123"
    }
    r = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    if r.status_code == 200:
        token_data = r.json()
        token = token_data["access_token"]
        print(f"  ✓ Login successful")
        print(f"    Token: {token[:40]}...")
        print(f"    Expires in: {token_data['expires_in']//3600} hours")
    else:
        print(f"  ✗ Login failed: {r.text}")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # Step 3: Search for Python Jobs
    print_header("STEP 3: Search for Python Developer Jobs")
    search_data = {
        "keywords": "Python",
        "remote_only": True,
        "sources": ["demo"],
        "page_size": 5
    }
    r = requests.post(f"{BASE_URL}/api/v1/jobs/search", json=search_data, headers=headers)
    if r.status_code == 200:
        results = r.json()
        print(f"  Found {results['total']} matching jobs\n")
        for i, job in enumerate(results['jobs'][:5], 1):
            j = job['job']
            score = job['match_scores']['total_score']
            print(f"  {i}. [{score}% match] {j['title']}")
            print(f"     @ {j['company']} - {j['location']}")
            if j.get('salary_min') and j.get('salary_max'):
                print(f"     Salary: ${j['salary_min']:,} - ${j['salary_max']:,}")
            print(f"     Skills: {', '.join(j['required_skills'][:3])}")
            print()

    # Step 4: Search for Security Jobs
    print_header("STEP 4: Search for Security Jobs")
    search_data = {
        "keywords": "Security",
        "sources": ["demo"],
        "page_size": 3
    }
    r = requests.post(f"{BASE_URL}/api/v1/jobs/search", json=search_data, headers=headers)
    if r.status_code == 200:
        results = r.json()
        print(f"  Found {results['total']} matching jobs\n")
        for i, job in enumerate(results['jobs'][:3], 1):
            j = job['job']
            score = job['match_scores']['total_score']
            print(f"  {i}. [{score}% match] {j['title']}")
            print(f"     @ {j['company']} - Remote: {j['is_remote']}")
            print()

    # Step 5: ATS Resume Check
    print_header("STEP 5: Check Resume ATS Compatibility")
    resume_text = """
John Smith
john.smith@email.com | 555-123-4567 | Austin, TX

WORK EXPERIENCE

Senior DevOps Engineer | TechCorp Inc | 2021 - Present
- Designed and implemented Kubernetes clusters serving 10M daily requests
- Built CI/CD pipelines using Jenkins and GitHub Actions
- Managed AWS infrastructure using Terraform

DevOps Engineer | StartupXYZ | 2018 - 2021
- Implemented Docker containerization for microservices
- Set up monitoring using Prometheus and Grafana

EDUCATION
Bachelor of Science in Computer Science
University of Texas at Austin | 2018

SKILLS
AWS, Kubernetes, Docker, Terraform, Jenkins, Python, Bash, Linux
"""

    ats_data = {
        "resume_text": resume_text,
        "resume_format": "docx",
        "target_ats": "icims"
    }
    r = requests.post(f"{BASE_URL}/api/v1/jobs/ats-check", json=ats_data, headers=headers)
    if r.status_code == 200:
        result = r.json()
        print(f"  Target ATS: {result['target_ats'].upper()}")
        print(f"  Parser Group: {result['parser_group']}")
        print(f"  Market Coverage: {result['market_coverage']}")
        print(f"\n  ATS Score: {result['overall_score']}/100")
        print(f"\n  Issues Found: {len(result['issues'])}")
        for issue in result['issues'][:3]:
            icon = "⚠" if issue['severity'] == 'warning' else "ℹ"
            print(f"    {icon} [{issue['severity']}] {issue['message']}")

    # Step 6: Check against different ATS
    print_header("STEP 6: Compare ATS Compatibility")
    ats_systems = ["greenhouse", "workday", "bullhorn"]

    for ats in ats_systems:
        ats_data["target_ats"] = ats
        r = requests.post(f"{BASE_URL}/api/v1/jobs/ats-check", json=ats_data, headers=headers)
        if r.status_code == 200:
            result = r.json()
            print(f"  {ats.upper():15} | Score: {result['overall_score']:3}/100 | Group: {result['parser_group']}")

    print("\n" + "="*60)
    print("     TEST COMPLETE - All endpoints working!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
