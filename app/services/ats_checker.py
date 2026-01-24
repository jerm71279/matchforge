"""
MatchForge ATS Checker Service
Validates resume format against known ATS parsing requirements
"""
import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class Severity(Enum):
    ERROR = "error"       # Will likely fail parsing
    WARNING = "warning"   # May cause issues
    INFO = "info"         # Suggestion for improvement


@dataclass
class ATSIssue:
    severity: Severity
    category: str
    message: str
    suggestion: str
    line_number: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "suggestion": self.suggestion,
        }


class ATSChecker:
    """
    Checks resume for ATS compatibility issues.
    Targets top 10 ATS systems covering ~56% market share (Grok-verified Jan 2026)

    Parser Groups:
    - Legacy-Strict: iCIMS, Taleo, SAP SuccessFactors (~21-22%)
    - Modern-Cloud: Greenhouse, Lever, SmartRecruiters (~14-15%)
    - HCM-Integrated: Workday, ADP, Ceridian (~17-20%)
    - Staffing-Specific: Bullhorn (~1-1.5%)
    """

    STANDARD_HEADERS = {
        "experience": ["work experience", "professional experience", "experience", "employment history", "work history"],
        "education": ["education", "academic background", "educational background"],
        "skills": ["skills", "technical skills", "core competencies", "competencies"],
        "summary": ["summary", "professional summary", "objective", "profile"],
        "certifications": ["certifications", "licenses", "credentials"],
        "availability": ["availability", "start date", "notice period"],  # For staffing ATS
    }

    PROBLEMATIC_HEADERS = [
        "my journey", "what i bring", "why me", "career highlights",
        "about me", "my story", "the path", "my expertise"
    ]

    # Parser group definitions for strategy selection
    PARSER_GROUPS = {
        "legacy_strict": {
            "systems": ["icims", "taleo", "successfactors"],
            "coverage": "20-25%",
            "characteristics": "Strict headers, .docx preferred, keyword-heavy scoring",
        },
        "modern_cloud": {
            "systems": ["greenhouse", "lever", "smartrecruiters"],
            "coverage": "15-18%",
            "characteristics": "Forgiving parsers, good PDF support, AI-enhanced matching",
        },
        "hcm_integrated": {
            "systems": ["workday", "adp", "ceridian"],
            "coverage": "12-15%",
            "characteristics": "Part of HR suite, skills section critical, structured data focus",
        },
        "staffing_specific": {
            "systems": ["bullhorn"],
            "coverage": "2-3%",
            "characteristics": "Agency workflows, availability/rate info expected, quick placement focus",
        },
    }

    # Top 10 ATS behaviors (~56% combined market share - Grok-verified January 2026)
    ATS_BEHAVIORS = {
        # Legacy-Strict Group (~20-25% market share)
        "icims": {
            "market_share": "10.7%",
            "parser_group": "legacy_strict",
            "strict_headers": True,
            "pdf_support": "limited",
            "table_support": False,
            "header_footer_parsing": False,
            "keyword_scoring": True,
            "tips": ["Use .docx format", "Include exact keyword matches", "Standard section headers only"],
        },
        "taleo": {
            "market_share": "8-9%",
            "parser_group": "legacy_strict",
            "strict_headers": True,
            "pdf_support": "text-only",
            "table_support": False,
            "header_footer_parsing": False,
            "keyword_scoring": True,
            "tips": ["Spell out acronyms", "Use chronological format", "Avoid graphics completely"],
        },
        "successfactors": {
            "market_share": "2-3%",
            "parser_group": "legacy_strict",
            "strict_headers": True,
            "pdf_support": "limited",
            "table_support": False,
            "header_footer_parsing": False,
            "keyword_scoring": True,
            "tips": ["SAP ecosystem alignment", "Structured competency sections", "Clear job titles"],
        },
        # Modern-Cloud Group (~15-18% market share)
        "greenhouse": {
            "market_share": "6-7%",
            "parser_group": "modern_cloud",
            "strict_headers": False,
            "pdf_support": "good",
            "table_support": "limited",
            "header_footer_parsing": True,
            "keyword_scoring": False,
            "tips": ["PDF acceptable", "Focus on skills alignment", "Startup-friendly formatting"],
        },
        "lever": {
            "market_share": "4-5%",
            "parser_group": "modern_cloud",
            "strict_headers": False,
            "pdf_support": "good",
            "table_support": "limited",
            "header_footer_parsing": True,
            "keyword_scoring": False,
            "tips": ["Modern formatting OK", "Highlight collaboration skills", "Include GitHub/portfolio links"],
        },
        "smartrecruiters": {
            "market_share": "3-4%",
            "parser_group": "modern_cloud",
            "strict_headers": False,
            "pdf_support": "good",
            "table_support": "limited",
            "header_footer_parsing": True,
            "keyword_scoring": False,
            "tips": ["AI-enhanced matching", "Skills-based emphasis", "Clear impact metrics"],
        },
        # HCM-Integrated Group (~12-15% market share)
        "workday": {
            "market_share": "12-14%",  # Grok-verified Jan 2026
            "parser_group": "hcm_integrated",
            "strict_headers": False,
            "pdf_support": "good",
            "table_support": "limited",
            "header_footer_parsing": True,
            "keyword_scoring": False,
            "skills_section_critical": True,
            "tips": ["Strong skills section required", "Structured experience format", "Clear career progression"],
        },
        "adp": {
            "market_share": "3%",
            "parser_group": "hcm_integrated",
            "strict_headers": False,
            "pdf_support": "good",
            "table_support": "limited",
            "header_footer_parsing": True,
            "keyword_scoring": False,
            "skills_section_critical": True,
            "tips": ["SMB/mid-market focus", "Compliance-friendly format", "Clear dates and titles"],
        },
        "ceridian": {
            "market_share": "2-3%",
            "parser_group": "hcm_integrated",
            "strict_headers": False,
            "pdf_support": "good",
            "table_support": "limited",
            "header_footer_parsing": True,
            "keyword_scoring": False,
            "skills_section_critical": True,
            "tips": ["Dayforce ecosystem", "Workforce management alignment", "Clear availability"],
        },
        # Staffing-Specific Group (~1-1.5% market share)
        "bullhorn": {
            "market_share": "1-1.5%",  # Grok-verified Jan 2026
            "parser_group": "staffing_specific",
            "strict_headers": False,
            "pdf_support": "good",
            "table_support": "limited",
            "header_footer_parsing": True,
            "keyword_scoring": True,
            "availability_expected": True,
            "tips": ["Include availability/start date", "Rate expectations if contract", "Recruiter-friendly format"],
        },
    }

    def check_resume(self, resume_text: str, resume_format: str = "docx") -> list[ATSIssue]:
        """
        Run all ATS checks on resume text.

        Args:
            resume_text: Extracted text from resume
            resume_format: File format (docx, pdf, txt)

        Returns:
            List of ATS issues found
        """
        issues = []

        issues.extend(self._check_format(resume_format))
        issues.extend(self._check_section_headers(resume_text))
        issues.extend(self._check_contact_info(resume_text))
        issues.extend(self._check_special_characters(resume_text))
        issues.extend(self._check_tables_columns(resume_text))
        issues.extend(self._check_dates(resume_text))
        issues.extend(self._check_acronyms(resume_text))
        issues.extend(self._check_length(resume_text))

        return issues

    def _check_format(self, format: str) -> list[ATSIssue]:
        """Check file format compatibility."""
        issues = []

        if format.lower() == "pdf":
            issues.append(ATSIssue(
                severity=Severity.WARNING,
                category="format",
                message="PDF format detected",
                suggestion="DOCX is preferred for maximum ATS compatibility. If using PDF, ensure it's text-based (not scanned)."
            ))
        elif format.lower() not in ["docx", "doc", "txt"]:
            issues.append(ATSIssue(
                severity=Severity.ERROR,
                category="format",
                message=f"Unsupported format: {format}",
                suggestion="Use DOCX or TXT format for best ATS compatibility."
            ))

        return issues

    def _check_section_headers(self, text: str) -> list[ATSIssue]:
        """Check for standard vs problematic section headers."""
        issues = []
        text_lower = text.lower()

        found_sections = set()
        for section, variations in self.STANDARD_HEADERS.items():
            for var in variations:
                if var in text_lower:
                    found_sections.add(section)
                    break

        if "experience" not in found_sections:
            issues.append(ATSIssue(
                severity=Severity.ERROR,
                category="structure",
                message="Missing 'Experience' or 'Work Experience' section header",
                suggestion="Add a clearly labeled 'Work Experience' or 'Professional Experience' section."
            ))

        if "education" not in found_sections:
            issues.append(ATSIssue(
                severity=Severity.WARNING,
                category="structure",
                message="Missing 'Education' section header",
                suggestion="Add a clearly labeled 'Education' section, even if brief."
            ))

        for header in self.PROBLEMATIC_HEADERS:
            if header in text_lower:
                issues.append(ATSIssue(
                    severity=Severity.WARNING,
                    category="structure",
                    message=f"Non-standard header found: '{header}'",
                    suggestion="Use standard headers like 'Work Experience', 'Education', 'Skills' for better parsing."
                ))

        return issues

    def _check_contact_info(self, text: str) -> list[ATSIssue]:
        """Check for contact information."""
        issues = []

        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        if not re.search(email_pattern, text):
            issues.append(ATSIssue(
                severity=Severity.ERROR,
                category="contact",
                message="No email address found",
                suggestion="Include a clearly visible email address."
            ))

        phone_pattern = r'[\d\-\(\)\s\.]{10,}'
        if not re.search(phone_pattern, text):
            issues.append(ATSIssue(
                severity=Severity.WARNING,
                category="contact",
                message="No phone number found",
                suggestion="Include a phone number for employer contact."
            ))

        return issues

    def _check_special_characters(self, text: str) -> list[ATSIssue]:
        """Check for special characters that may not parse correctly."""
        issues = []

        problematic = {
            "→": "arrow", "★": "star", "✓": "checkmark",
            "©": "copyright", "®": "registered", "™": "trademark",
            "▪": "square bullet", "◦": "hollow bullet"
        }

        found = [name for char, name in problematic.items() if char in text]

        if found:
            issues.append(ATSIssue(
                severity=Severity.WARNING,
                category="content",
                message=f"Special characters found: {', '.join(found)}",
                suggestion="Some ATS may not parse special characters. Use standard dashes (-) or asterisks (*) for bullets."
            ))

        return issues

    def _check_tables_columns(self, text: str) -> list[ATSIssue]:
        """Heuristic check for table-like content."""
        issues = []
        lines = text.split('\n')
        tab_heavy_lines = sum(1 for line in lines if line.count('\t') >= 2)

        if tab_heavy_lines > 5:
            issues.append(ATSIssue(
                severity=Severity.WARNING,
                category="layout",
                message="Possible table or multi-column layout detected",
                suggestion="Avoid tables and multi-column layouts. ATS reads left-to-right, top-to-bottom."
            ))

        return issues

    def _check_dates(self, text: str) -> list[ATSIssue]:
        """Check for consistent date formatting."""
        issues = []

        patterns = {
            "MM/YYYY": r'\b\d{1,2}/\d{4}\b',
            "Month YYYY": r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b',
            "Mon YYYY": r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b',
        }

        found_formats = [name for name, pattern in patterns.items() if re.search(pattern, text, re.IGNORECASE)]

        if len(found_formats) > 1:
            issues.append(ATSIssue(
                severity=Severity.INFO,
                category="content",
                message=f"Multiple date formats: {', '.join(found_formats)}",
                suggestion="Use consistent date formatting throughout (e.g., 'January 2024' or '01/2024')."
            ))

        return issues

    def _check_acronyms(self, text: str) -> list[ATSIssue]:
        """Check for acronyms that should have full forms."""
        issues = []

        acronyms = {
            "SEO": "Search Engine Optimization",
            "API": "Application Programming Interface",
            "AWS": "Amazon Web Services",
            "SQL": "Structured Query Language",
            "CI/CD": "Continuous Integration/Continuous Deployment",
        }

        suggestions = []
        for acronym, full_form in acronyms.items():
            if acronym in text and full_form.lower() not in text.lower():
                suggestions.append(f"{full_form} ({acronym})")

        if suggestions:
            issues.append(ATSIssue(
                severity=Severity.INFO,
                category="keywords",
                message="Found acronyms without full forms",
                suggestion=f"Include both acronym and full term. Example: {suggestions[0]}"
            ))

        return issues

    def _check_length(self, text: str) -> list[ATSIssue]:
        """Check resume length."""
        issues = []
        word_count = len(text.split())

        if word_count < 200:
            issues.append(ATSIssue(
                severity=Severity.WARNING,
                category="content",
                message="Resume appears too short",
                suggestion="Most effective resumes have 400-800 words. Consider adding more detail."
            ))
        elif word_count > 1500:
            issues.append(ATSIssue(
                severity=Severity.INFO,
                category="content",
                message="Resume may be too long",
                suggestion="Consider condensing to 1-2 pages for better readability."
            ))

        return issues

    def compute_ats_score(self, issues: list[ATSIssue]) -> int:
        """Compute overall ATS compatibility score (0-100)."""
        score = 100

        for issue in issues:
            if issue.severity == Severity.ERROR:
                score -= 20
            elif issue.severity == Severity.WARNING:
                score -= 10
            elif issue.severity == Severity.INFO:
                score -= 2

        return max(0, score)

    def suggest_keywords(self, resume_text: str, job_description: str) -> list[dict]:
        """Suggest missing keywords from job description."""
        job_keywords = self._extract_keywords(job_description)
        resume_lower = resume_text.lower()

        missing = []
        for keyword in job_keywords:
            if keyword.lower() not in resume_lower:
                missing.append({
                    "keyword": keyword,
                    "importance": "high" if self._is_likely_required(keyword, job_description) else "medium"
                })

        return missing[:10]

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract important keywords from job description."""
        keywords = set()

        skill_patterns = [
            r'(?:required|preferred|must have|experience with|knowledge of)[:\s]+([^\.]+)',
            r'(?:skills|requirements|qualifications)[:\s]+([^\.]+)',
        ]

        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                parts = re.split(r'[,;]|\band\b', match)
                for part in parts:
                    cleaned = part.strip()
                    if 2 < len(cleaned) < 50:
                        keywords.add(cleaned)

        return list(keywords)

    def _is_likely_required(self, keyword: str, job_description: str) -> bool:
        """Check if keyword appears in required sections."""
        text_lower = job_description.lower()
        keyword_lower = keyword.lower()

        for pattern in ['required', 'must have', 'essential', 'mandatory']:
            if pattern in text_lower:
                pattern_idx = text_lower.find(pattern)
                keyword_idx = text_lower.find(keyword_lower)
                if keyword_idx != -1 and abs(pattern_idx - keyword_idx) < 200:
                    return True
        return False

    def check_for_ats(self, resume_text: str, resume_format: str, target_ats: str) -> dict:
        """
        Check resume for a specific ATS system.

        Args:
            resume_text: Extracted text from resume
            resume_format: File format (docx, pdf, txt)
            target_ats: Target ATS system (e.g., 'icims', 'greenhouse')

        Returns:
            Dict with issues, score, tips, and parser group info
        """
        ats_config = self.ATS_BEHAVIORS.get(target_ats.lower())
        if not ats_config:
            return {
                "error": f"Unknown ATS: {target_ats}",
                "supported_systems": list(self.ATS_BEHAVIORS.keys())
            }

        # Run standard checks
        issues = self.check_resume(resume_text, resume_format)

        # Add ATS-specific checks
        issues.extend(self._check_ats_specific(resume_text, resume_format, target_ats, ats_config))

        return {
            "target_ats": target_ats,
            "market_share": ats_config.get("market_share"),
            "parser_group": ats_config.get("parser_group"),
            "issues": [i.to_dict() for i in issues],
            "score": self.compute_ats_score(issues),
            "tips": ats_config.get("tips", []),
            "parser_group_info": self.PARSER_GROUPS.get(ats_config.get("parser_group"), {}),
        }

    def _check_ats_specific(
        self,
        text: str,
        format: str,
        ats_name: str,
        config: dict
    ) -> list[ATSIssue]:
        """Run ATS-specific validation checks."""
        issues = []

        # Legacy-Strict: Enforce DOCX, strict headers
        if config.get("parser_group") == "legacy_strict":
            if format.lower() != "docx":
                issues.append(ATSIssue(
                    severity=Severity.ERROR,
                    category="format",
                    message=f"{ats_name.upper()} strongly prefers DOCX format",
                    suggestion="Convert to DOCX for best results with legacy ATS systems."
                ))

            if config.get("keyword_scoring"):
                word_count = len(text.split())
                unique_words = len(set(text.lower().split()))
                if unique_words / max(word_count, 1) > 0.7:
                    issues.append(ATSIssue(
                        severity=Severity.INFO,
                        category="keywords",
                        message="Low keyword repetition detected",
                        suggestion="Legacy ATS uses keyword density scoring. Naturally repeat key terms."
                    ))

        # HCM-Integrated: Require strong skills section
        if config.get("skills_section_critical"):
            text_lower = text.lower()
            skills_found = any(s in text_lower for s in ["skills", "technical skills", "core competencies"])
            if not skills_found:
                issues.append(ATSIssue(
                    severity=Severity.ERROR,
                    category="structure",
                    message=f"{ats_name.upper()} requires a dedicated Skills section",
                    suggestion="Add a clearly labeled 'Skills' or 'Technical Skills' section."
                ))

        # Staffing-Specific: Check for availability
        if config.get("availability_expected"):
            text_lower = text.lower()
            availability_found = any(
                term in text_lower
                for term in ["available", "start date", "notice period", "immediate", "contract"]
            )
            if not availability_found:
                issues.append(ATSIssue(
                    severity=Severity.WARNING,
                    category="content",
                    message="No availability information found",
                    suggestion="For staffing agencies, include availability/start date and contract preferences."
                ))

        return issues

    def check_for_parser_group(self, resume_text: str, resume_format: str, parser_group: str) -> dict:
        """
        Check resume against all systems in a parser group.

        Args:
            resume_text: Extracted text from resume
            resume_format: File format
            parser_group: Parser group name (legacy_strict, modern_cloud, hcm_integrated, staffing_specific)

        Returns:
            Dict with combined analysis for the parser group
        """
        group_config = self.PARSER_GROUPS.get(parser_group)
        if not group_config:
            return {
                "error": f"Unknown parser group: {parser_group}",
                "available_groups": list(self.PARSER_GROUPS.keys())
            }

        results = []
        for ats_name in group_config["systems"]:
            result = self.check_for_ats(resume_text, resume_format, ats_name)
            results.append(result)

        # Aggregate scores
        scores = [r["score"] for r in results if "score" in r]
        avg_score = sum(scores) / len(scores) if scores else 0

        # Collect unique issues
        all_issues = {}
        for r in results:
            for issue in r.get("issues", []):
                key = f"{issue['category']}:{issue['message']}"
                if key not in all_issues:
                    all_issues[key] = issue

        return {
            "parser_group": parser_group,
            "coverage": group_config["coverage"],
            "characteristics": group_config["characteristics"],
            "systems_checked": group_config["systems"],
            "average_score": round(avg_score),
            "individual_scores": {r["target_ats"]: r["score"] for r in results if "score" in r},
            "combined_issues": list(all_issues.values()),
            "group_tips": self._get_group_tips(parser_group),
        }

    def _get_group_tips(self, parser_group: str) -> list[str]:
        """Get optimization tips for a parser group."""
        tips = {
            "legacy_strict": [
                "Use .docx format exclusively",
                "Include exact job description keywords",
                "Use standard section headers (Work Experience, Education, Skills)",
                "Spell out all acronyms at least once",
                "Avoid all graphics, tables, and columns",
            ],
            "modern_cloud": [
                "PDF format is acceptable",
                "Focus on skills alignment over keyword matching",
                "Include portfolio/GitHub links",
                "Highlight collaboration and impact metrics",
                "Modern formatting is tolerated",
            ],
            "hcm_integrated": [
                "Prioritize a strong, detailed Skills section",
                "Show clear career progression",
                "Use structured, consistent formatting",
                "Include specific tools and technologies",
                "Dates and titles must be unambiguous",
            ],
            "staffing_specific": [
                "Include availability/start date prominently",
                "Note contract type preferences",
                "Include hourly/daily rate if applicable",
                "Highlight recent and relevant experience",
                "Make recruiter contact easy",
            ],
        }
        return tips.get(parser_group, [])

    def get_coverage_stats(self) -> dict:
        """Get market coverage statistics for supported ATS systems."""
        by_group = {}
        total_share = 0

        for ats_name, config in self.ATS_BEHAVIORS.items():
            group = config.get("parser_group", "unknown")
            share = config.get("market_share", "0%")

            if group not in by_group:
                by_group[group] = {"systems": [], "combined_share": 0}

            by_group[group]["systems"].append(ats_name)

            # Parse share for totaling (take lower bound of range)
            try:
                share_num = float(share.replace("%", "").split("-")[0])
                by_group[group]["combined_share"] += share_num
                total_share += share_num
            except:
                pass

        return {
            "total_systems": len(self.ATS_BEHAVIORS),
            "estimated_market_coverage": f"{total_share:.1f}%",
            "coverage_target": "~51% (top 10 systems)",
            "by_parser_group": {
                group: {
                    "systems": data["systems"],
                    "estimated_share": f"{data['combined_share']:.1f}%"
                }
                for group, data in by_group.items()
            },
            "remaining_coverage": {
                "universal_rules": "~10-15%",
                "note": "Additional coverage via parser-group-aligned universal rules"
            }
        }
