"""
SEC Filing Parser Module

Parses SEC filings (10-K, 10-Q, 8-K) to extract structured sections.
Handles HTML cleaning and section boundary detection.
"""

import re
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from dataclasses import dataclass


@dataclass
class ParsedSection:
    """Represents a parsed section from an SEC filing."""
    name: str
    title: str
    content: str
    start_index: int
    end_index: int


class SECFilingParser:
    """
    Parser for SEC filings (10-K, 10-Q, 8-K).
    
    Extracts structured sections from raw HTML filing content.
    """
    
    # 10-K section patterns (Item number -> display name)
    SECTION_10K = {
        "1": "Business",
        "1A": "Risk Factors",
        "1B": "Unresolved Staff Comments",
        "2": "Properties",
        "3": "Legal Proceedings",
        "4": "Mine Safety Disclosures",
        "5": "Market for Registrant's Common Equity",
        "6": "Reserved",
        "7": "Management's Discussion and Analysis",
        "7A": "Quantitative and Qualitative Disclosures About Market Risk",
        "8": "Financial Statements and Supplementary Data",
        "9": "Changes in and Disagreements With Accountants",
        "9A": "Controls and Procedures",
        "9B": "Other Information",
        "10": "Directors, Executive Officers and Corporate Governance",
        "11": "Executive Compensation",
        "12": "Security Ownership",
        "13": "Certain Relationships and Related Transactions",
        "14": "Principal Accountant Fees and Services",
        "15": "Exhibits and Financial Statement Schedules",
    }
    
    # 10-Q section patterns
    SECTION_10Q = {
        "1": "Financial Statements",
        "2": "Management's Discussion and Analysis",
        "3": "Quantitative and Qualitative Disclosures About Market Risk",
        "4": "Controls and Procedures",
    }
    
    # 8-K item patterns (material events)
    SECTION_8K = {
        "1.01": "Entry into a Material Definitive Agreement",
        "1.02": "Termination of a Material Definitive Agreement",
        "1.03": "Bankruptcy or Receivership",
        "2.01": "Completion of Acquisition or Disposition of Assets",
        "2.02": "Results of Operations and Financial Condition",
        "2.03": "Creation of a Direct Financial Obligation",
        "2.04": "Triggering Events That Accelerate or Increase a Direct Financial Obligation",
        "2.05": "Costs Associated with Exit or Disposal Activities",
        "2.06": "Material Impairments",
        "3.01": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule",
        "3.02": "Unregistered Sales of Equity Securities",
        "3.03": "Material Modification to Rights of Security Holders",
        "4.01": "Changes in Registrant's Certifying Accountant",
        "4.02": "Non-Reliance on Previously Issued Financial Statements",
        "5.01": "Changes in Control of Registrant",
        "5.02": "Departure of Directors or Certain Officers",
        "5.03": "Amendments to Articles of Incorporation or Bylaws",
        "5.04": "Temporary Suspension of Trading Under Registrant's Employee Benefit Plans",
        "5.05": "Amendment to Registrant's Code of Ethics",
        "5.06": "Change in Shell Company Status",
        "5.07": "Submission of Matters to a Vote of Security Holders",
        "5.08": "Shareholder Nominations",
        "7.01": "Regulation FD Disclosure",
        "8.01": "Other Events",
        "9.01": "Financial Statements and Exhibits",
    }
    
    def __init__(self):
        """Initialize the parser."""
        pass
    
    def clean_html(self, html_content: str) -> str:
        """
        Clean HTML content by removing scripts, styles, and excessive whitespace.
        
        Args:
            html_content: Raw HTML string from SEC filing
            
        Returns:
            Cleaned text content without HTML tags
        """
        if not html_content:
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove script and style elements
        for element in soup(["script", "style", "meta", "link", "noscript"]):
            element.decompose()
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, type(soup.new_string("")))):
            if hasattr(comment, 'extract') and str(comment).strip().startswith('<!--'):
                comment.extract()
        
        # Get text content
        text = soup.get_text(separator=" ")
        
        # Clean up whitespace
        text = self._normalize_whitespace(text)
        
        return text
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace in text.
        
        - Replace multiple spaces with single space
        - Replace multiple newlines with double newline
        - Strip leading/trailing whitespace
        """
        # Replace tabs and other whitespace with spaces
        text = re.sub(r'[\t\r\f\v]+', ' ', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Replace 3+ newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Strip whitespace from each line
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # Remove empty lines at start/end
        text = text.strip()
        
        return text
    
    def _find_section_boundaries(
        self, 
        text: str, 
        section_patterns: Dict[str, str],
        filing_type: str
    ) -> List[Tuple[str, int, int]]:
        """
        Find section boundaries in the text.
        
        Args:
            text: Cleaned text content
            section_patterns: Dict mapping section IDs to names
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            
        Returns:
            List of tuples (section_id, start_index, end_index)
        """
        boundaries = []
        
        for section_id, section_name in section_patterns.items():
            # Build multiple regex patterns for section header (more flexible)
            patterns = []
            
            if filing_type == "8-K":
                # 8-K uses "Item X.XX" format
                patterns = [
                    rf'(?:^|\n)\s*ITEM\s+{re.escape(section_id)}[.\s:\-]*',
                    rf'(?:^|\n)\s*{re.escape(section_id)}[.\s:\-]+{re.escape(section_name[:15])}',
                ]
            else:
                # 10-K and 10-Q use "Item X" or "ITEM X" format
                # Handle variations like "Item 1A", "ITEM 1A.", "Item 1A -", "Item 1A:"
                section_id_pattern = re.escape(section_id).replace(r'\-', r'[\-]?')
                patterns = [
                    rf'(?:^|\n)\s*ITEM\s+{section_id_pattern}[.\s:\-]+',
                    rf'(?:^|\n)\s*ITEM\s+{section_id_pattern}\s*$',
                    rf'(?:^|\n)\s*ITEM\s+{section_id_pattern}\s+{re.escape(section_name[:10])}',
                ]
            
            all_matches = []
            for pattern in patterns:
                matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
                all_matches.extend(matches)
            
            if all_matches:
                # Deduplicate by position (within 50 chars)
                unique_matches = []
                for match in sorted(all_matches, key=lambda m: m.start()):
                    if not unique_matches or match.start() - unique_matches[-1].start() > 50:
                        unique_matches.append(match)
                
                # Use the last match (often the actual content, not table of contents)
                # But prefer matches that are followed by substantial content
                best_match = None
                for match in reversed(unique_matches):
                    # Check if there's substantial content after this match
                    remaining = text[match.end():match.end() + 1000]
                    # Look for actual paragraph content, not just more headers
                    if len(remaining.strip()) > 200 and not remaining.strip()[:50].upper().startswith('ITEM'):
                        best_match = match
                        break
                
                if best_match is None and unique_matches:
                    best_match = unique_matches[-1]
                
                if best_match:
                    boundaries.append((section_id, best_match.start(), -1))
        
        # Sort by start position
        boundaries.sort(key=lambda x: x[1])
        
        # Calculate end positions (start of next section or end of text)
        result = []
        for i, (section_id, start, _) in enumerate(boundaries):
            if i + 1 < len(boundaries):
                end = boundaries[i + 1][1]
            else:
                end = len(text)
            result.append((section_id, start, end))
        
        return result
    
    def _extract_section(
        self, 
        text: str, 
        section_id: str, 
        start: int, 
        end: int,
        section_patterns: Dict[str, str]
    ) -> ParsedSection:
        """
        Extract a section from text given boundaries.
        
        Args:
            text: Full text content
            section_id: Section identifier (e.g., "1A")
            start: Start index
            end: End index
            section_patterns: Dict mapping section IDs to names
            
        Returns:
            ParsedSection object
        """
        content = text[start:end].strip()
        
        # Remove the section header from content
        lines = content.split('\n')
        if lines:
            # Skip first line if it's just the header
            first_line = lines[0].strip().upper()
            if f"ITEM {section_id}" in first_line or section_id in first_line:
                content = '\n'.join(lines[1:]).strip()
        
        return ParsedSection(
            name=section_id,
            title=section_patterns.get(section_id, f"Item {section_id}"),
            content=content,
            start_index=start,
            end_index=end
        )
    
    def parse_10k(self, html_content: str) -> Dict[str, ParsedSection]:
        """
        Parse a 10-K filing and extract key sections.
        
        Extracts: Item 1 (Business), 1A (Risk Factors), 7 (MD&A), 
                  7A (Market Risk), 8 (Financial Statements)
        
        Args:
            html_content: Raw HTML content of 10-K filing
            
        Returns:
            Dict mapping section IDs to ParsedSection objects
        """
        # Clean HTML
        text = self.clean_html(html_content)
        
        if not text:
            return {}
        
        # Target sections for 10-K analysis
        target_sections = {"1", "1A", "7", "7A", "8"}
        
        # Find all section boundaries
        boundaries = self._find_section_boundaries(text, self.SECTION_10K, "10-K")
        
        # Extract target sections
        result = {}
        for section_id, start, end in boundaries:
            if section_id in target_sections:
                result[section_id] = self._extract_section(
                    text, section_id, start, end, self.SECTION_10K
                )
        
        return result
    
    def parse_10q(self, html_content: str) -> Dict[str, ParsedSection]:
        """
        Parse a 10-Q filing and extract key sections.
        
        Extracts: Part I Item 2 (MD&A), Item 3 (Market Risk)
        
        Args:
            html_content: Raw HTML content of 10-Q filing
            
        Returns:
            Dict mapping section IDs to ParsedSection objects
        """
        # Clean HTML
        text = self.clean_html(html_content)
        
        if not text:
            return {}
        
        # Find section boundaries
        boundaries = self._find_section_boundaries(text, self.SECTION_10Q, "10-Q")
        
        # Extract all found sections
        result = {}
        for section_id, start, end in boundaries:
            result[section_id] = self._extract_section(
                text, section_id, start, end, self.SECTION_10Q
            )
        
        return result
    
    def parse_8k(self, html_content: str) -> Dict[str, ParsedSection]:
        """
        Parse an 8-K filing and extract material event sections.
        
        8-K filings report material events like:
        - Results of operations (2.02)
        - Departure of officers (5.02)
        - Other events (8.01)
        
        Args:
            html_content: Raw HTML content of 8-K filing
            
        Returns:
            Dict mapping section IDs to ParsedSection objects
        """
        # Clean HTML
        text = self.clean_html(html_content)
        
        if not text:
            return {}
        
        # Find section boundaries
        boundaries = self._find_section_boundaries(text, self.SECTION_8K, "8-K")
        
        # Extract all found sections
        result = {}
        for section_id, start, end in boundaries:
            result[section_id] = self._extract_section(
                text, section_id, start, end, self.SECTION_8K
            )
        
        return result
    
    def parse(self, html_content: str, filing_type: str) -> Dict[str, ParsedSection]:
        """
        Parse an SEC filing based on its type.
        
        Args:
            html_content: Raw HTML content
            filing_type: One of "10-K", "10-Q", "8-K"
            
        Returns:
            Dict mapping section IDs to ParsedSection objects
            
        Raises:
            ValueError: If filing_type is not recognized
        """
        filing_type = filing_type.upper()
        
        if filing_type == "10-K":
            return self.parse_10k(html_content)
        elif filing_type == "10-Q":
            return self.parse_10q(html_content)
        elif filing_type == "8-K":
            return self.parse_8k(html_content)
        else:
            raise ValueError(f"Unknown filing type: {filing_type}. Expected 10-K, 10-Q, or 8-K")
    
    def get_risk_factors(self, html_content: str, filing_type: str = "10-K") -> Optional[str]:
        """
        Convenience method to extract just the Risk Factors section.
        
        Args:
            html_content: Raw HTML content
            filing_type: Filing type (default: 10-K)
            
        Returns:
            Risk factors text content, or None if not found
        """
        sections = self.parse(html_content, filing_type)
        
        if "1A" in sections:
            return sections["1A"].content
        
        return None
    
    def get_mda(self, html_content: str, filing_type: str = "10-K") -> Optional[str]:
        """
        Convenience method to extract Management's Discussion and Analysis.
        
        Args:
            html_content: Raw HTML content
            filing_type: Filing type (10-K or 10-Q)
            
        Returns:
            MD&A text content, or None if not found
        """
        sections = self.parse(html_content, filing_type)
        
        # MD&A is Item 7 in 10-K, Item 2 in 10-Q
        if filing_type.upper() == "10-K" and "7" in sections:
            return sections["7"].content
        elif filing_type.upper() == "10-Q" and "2" in sections:
            return sections["2"].content
        
        return None
