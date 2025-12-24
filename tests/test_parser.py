"""
Unit tests for SEC Filing Parser.

Tests HTML cleaning, section extraction, and parsing for 10-K, 10-Q, and 8-K filings.
"""

import pytest
from src.data.parser import SECFilingParser, ParsedSection


class TestHTMLCleaning:
    """Tests for HTML cleaning functionality."""
    
    def setup_method(self):
        """Set up parser instance for each test."""
        self.parser = SECFilingParser()
    
    def test_clean_html_removes_script_tags(self):
        """Test that script tags are removed."""
        html = """
        <html>
        <head><script>alert('test');</script></head>
        <body>
            <p>Important content</p>
            <script type="text/javascript">var x = 1;</script>
        </body>
        </html>
        """
        result = self.parser.clean_html(html)
        
        assert "alert" not in result
        assert "var x" not in result
        assert "Important content" in result
    
    def test_clean_html_removes_style_tags(self):
        """Test that style tags are removed."""
        html = """
        <html>
        <head><style>.class { color: red; }</style></head>
        <body>
            <p>Visible text</p>
            <style>body { margin: 0; }</style>
        </body>
        </html>
        """
        result = self.parser.clean_html(html)
        
        assert "color: red" not in result
        assert "margin: 0" not in result
        assert "Visible text" in result
    
    def test_clean_html_removes_meta_and_link_tags(self):
        """Test that meta and link tags are removed."""
        html = """
        <html>
        <head>
            <meta charset="utf-8">
            <link rel="stylesheet" href="style.css">
        </head>
        <body><p>Content here</p></body>
        </html>
        """
        result = self.parser.clean_html(html)
        
        assert "charset" not in result
        assert "stylesheet" not in result
        assert "Content here" in result
    
    def test_clean_html_normalizes_whitespace(self):
        """Test that excessive whitespace is normalized."""
        html = """
        <html><body>
            <p>First    paragraph</p>
            
            
            
            <p>Second paragraph</p>
        </body></html>
        """
        result = self.parser.clean_html(html)
        
        # Multiple spaces should be reduced to single space
        assert "First paragraph" in result or "First paragraph" in result
        # Multiple newlines should be reduced
        assert "\n\n\n" not in result
    
    def test_clean_html_empty_input(self):
        """Test handling of empty input."""
        assert self.parser.clean_html("") == ""
        assert self.parser.clean_html(None) == ""
    
    def test_clean_html_no_tags(self):
        """Test that text without HTML tags is preserved."""
        text = "Plain text without any HTML tags."
        result = self.parser.clean_html(text)
        
        assert "Plain text without any HTML tags" in result


class TestParse10K:
    """Tests for 10-K filing parsing."""
    
    def setup_method(self):
        """Set up parser instance for each test."""
        self.parser = SECFilingParser()
    
    def test_parse_10k_extracts_risk_factors(self):
        """Test extraction of Item 1A Risk Factors section."""
        html = """
        <html><body>
            <h2>ITEM 1. BUSINESS</h2>
            <p>We are a technology company.</p>
            
            <h2>ITEM 1A. RISK FACTORS</h2>
            <p>Investing in our securities involves significant risks.</p>
            <p>Competition risk: We face intense competition.</p>
            <p>Regulatory risk: Changes in regulations may affect us.</p>
            
            <h2>ITEM 2. PROPERTIES</h2>
            <p>Our headquarters is located in California.</p>
        </body></html>
        """
        result = self.parser.parse_10k(html)
        
        assert "1A" in result
        assert "significant risks" in result["1A"].content
        assert "Competition risk" in result["1A"].content
        assert result["1A"].title == "Risk Factors"
    
    def test_parse_10k_extracts_mda(self):
        """Test extraction of Item 7 MD&A section."""
        html = """
        <html><body>
            <h2>ITEM 6. RESERVED</h2>
            <p>Reserved.</p>
            
            <h2>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</h2>
            <p>The following discussion should be read in conjunction with our financial statements.</p>
            <p>Revenue increased 25% year over year.</p>
            
            <h2>ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES</h2>
            <p>We are exposed to market risk.</p>
        </body></html>
        """
        result = self.parser.parse_10k(html)
        
        assert "7" in result
        assert "Revenue increased" in result["7"].content
        assert "Management's Discussion and Analysis" in result["7"].title
    
    def test_parse_10k_extracts_market_risk(self):
        """Test extraction of Item 7A Market Risk section."""
        html = """
        <html><body>
            <h2>ITEM 7. MANAGEMENT'S DISCUSSION</h2>
            <p>Overview of operations.</p>
            
            <h2>ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK</h2>
            <p>Interest rate risk affects our borrowing costs.</p>
            <p>Foreign currency risk impacts international operations.</p>
            
            <h2>ITEM 8. FINANCIAL STATEMENTS</h2>
            <p>See consolidated financial statements.</p>
        </body></html>
        """
        result = self.parser.parse_10k(html)
        
        assert "7A" in result
        assert "Interest rate risk" in result["7A"].content
    
    def test_parse_10k_empty_content(self):
        """Test handling of empty content."""
        result = self.parser.parse_10k("")
        assert result == {}
    
    def test_parse_10k_no_matching_sections(self):
        """Test handling when no sections match."""
        html = "<html><body><p>Random content without section headers.</p></body></html>"
        result = self.parser.parse_10k(html)
        
        # Should return empty dict or dict without target sections
        assert isinstance(result, dict)


class TestParse10Q:
    """Tests for 10-Q filing parsing."""
    
    def setup_method(self):
        """Set up parser instance for each test."""
        self.parser = SECFilingParser()
    
    def test_parse_10q_extracts_mda(self):
        """Test extraction of MD&A section from 10-Q."""
        html = """
        <html><body>
            <h2>ITEM 1. FINANCIAL STATEMENTS</h2>
            <p>See attached financial statements.</p>
            
            <h2>ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS</h2>
            <p>Quarterly revenue was $500 million, up 15% from prior quarter.</p>
            <p>Operating expenses decreased due to cost optimization.</p>
            
            <h2>ITEM 3. QUANTITATIVE AND QUALITATIVE DISCLOSURES</h2>
            <p>Market risk disclosures.</p>
        </body></html>
        """
        result = self.parser.parse_10q(html)
        
        assert "2" in result
        assert "Quarterly revenue" in result["2"].content
        assert "Management's Discussion and Analysis" in result["2"].title
    
    def test_parse_10q_extracts_market_risk(self):
        """Test extraction of market risk section from 10-Q."""
        html = """
        <html><body>
            <h2>ITEM 2. MANAGEMENT'S DISCUSSION</h2>
            <p>Discussion content.</p>
            
            <h2>ITEM 3. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK</h2>
            <p>We hedge foreign currency exposure using forward contracts.</p>
            
            <h2>ITEM 4. CONTROLS AND PROCEDURES</h2>
            <p>Our disclosure controls are effective.</p>
        </body></html>
        """
        result = self.parser.parse_10q(html)
        
        assert "3" in result
        assert "hedge foreign currency" in result["3"].content
    
    def test_parse_10q_empty_content(self):
        """Test handling of empty content."""
        result = self.parser.parse_10q("")
        assert result == {}


class TestParse8K:
    """Tests for 8-K filing parsing."""
    
    def setup_method(self):
        """Set up parser instance for each test."""
        self.parser = SECFilingParser()
    
    def test_parse_8k_extracts_results_of_operations(self):
        """Test extraction of Item 2.02 Results of Operations."""
        html = """
        <html><body>
            <h2>Item 2.02 Results of Operations and Financial Condition</h2>
            <p>On January 15, 2024, the Company issued a press release announcing 
            its financial results for the fourth quarter ended December 31, 2023.</p>
            <p>Revenue for Q4 2023 was $1.2 billion.</p>
            
            <h2>Item 9.01 Financial Statements and Exhibits</h2>
            <p>(d) Exhibits</p>
        </body></html>
        """
        result = self.parser.parse_8k(html)
        
        assert "2.02" in result
        assert "financial results" in result["2.02"].content
        assert "Results of Operations" in result["2.02"].title
    
    def test_parse_8k_extracts_officer_departure(self):
        """Test extraction of Item 5.02 Departure of Officers."""
        html = """
        <html><body>
            <h2>Item 5.02 Departure of Directors or Certain Officers</h2>
            <p>On February 1, 2024, John Smith resigned as Chief Financial Officer 
            effective March 1, 2024. Jane Doe has been appointed as interim CFO.</p>
            
            <h2>Item 9.01 Financial Statements and Exhibits</h2>
            <p>Exhibits attached.</p>
        </body></html>
        """
        result = self.parser.parse_8k(html)
        
        assert "5.02" in result
        assert "resigned" in result["5.02"].content or "John Smith" in result["5.02"].content
    
    def test_parse_8k_extracts_other_events(self):
        """Test extraction of Item 8.01 Other Events."""
        html = """
        <html><body>
            <h2>Item 8.01 Other Events</h2>
            <p>The Company announced a new strategic partnership with XYZ Corp 
            to expand into international markets.</p>
            
            <h2>Item 9.01 Financial Statements and Exhibits</h2>
            <p>No exhibits.</p>
        </body></html>
        """
        result = self.parser.parse_8k(html)
        
        assert "8.01" in result
        assert "strategic partnership" in result["8.01"].content
    
    def test_parse_8k_empty_content(self):
        """Test handling of empty content."""
        result = self.parser.parse_8k("")
        assert result == {}


class TestGenericParse:
    """Tests for the generic parse method."""
    
    def setup_method(self):
        """Set up parser instance for each test."""
        self.parser = SECFilingParser()
    
    def test_parse_routes_to_10k(self):
        """Test that parse routes to parse_10k for 10-K filings."""
        html = """
        <html><body>
            <h2>ITEM 1A. RISK FACTORS</h2>
            <p>Risk content here.</p>
        </body></html>
        """
        result = self.parser.parse(html, "10-K")
        
        assert "1A" in result
    
    def test_parse_routes_to_10q(self):
        """Test that parse routes to parse_10q for 10-Q filings."""
        html = """
        <html><body>
            <h2>ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS</h2>
            <p>Quarterly discussion.</p>
        </body></html>
        """
        result = self.parser.parse(html, "10-Q")
        
        assert "2" in result
    
    def test_parse_routes_to_8k(self):
        """Test that parse routes to parse_8k for 8-K filings."""
        html = """
        <html><body>
            <h2>Item 8.01 Other Events</h2>
            <p>Event description.</p>
        </body></html>
        """
        result = self.parser.parse(html, "8-K")
        
        assert "8.01" in result
    
    def test_parse_case_insensitive(self):
        """Test that filing type is case insensitive."""
        html = "<html><body><h2>ITEM 1A. RISK FACTORS</h2><p>Risks.</p></body></html>"
        
        result_upper = self.parser.parse(html, "10-K")
        result_lower = self.parser.parse(html, "10-k")
        
        assert result_upper.keys() == result_lower.keys()
    
    def test_parse_invalid_filing_type(self):
        """Test that invalid filing type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown filing type"):
            self.parser.parse("<html></html>", "10-X")


class TestConvenienceMethods:
    """Tests for convenience methods."""
    
    def setup_method(self):
        """Set up parser instance for each test."""
        self.parser = SECFilingParser()
    
    def test_get_risk_factors(self):
        """Test get_risk_factors convenience method."""
        html = """
        <html><body>
            <h2>ITEM 1A. RISK FACTORS</h2>
            <p>Our business faces several risks including market volatility.</p>
        </body></html>
        """
        result = self.parser.get_risk_factors(html)
        
        assert result is not None
        assert "market volatility" in result
    
    def test_get_risk_factors_not_found(self):
        """Test get_risk_factors when section not found."""
        html = "<html><body><p>No risk factors section.</p></body></html>"
        result = self.parser.get_risk_factors(html)
        
        assert result is None
    
    def test_get_mda_10k(self):
        """Test get_mda for 10-K filing."""
        html = """
        <html><body>
            <h2>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</h2>
            <p>Revenue growth was driven by new product launches.</p>
        </body></html>
        """
        result = self.parser.get_mda(html, "10-K")
        
        assert result is not None
        assert "Revenue growth" in result
    
    def test_get_mda_10q(self):
        """Test get_mda for 10-Q filing."""
        html = """
        <html><body>
            <h2>ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS</h2>
            <p>Quarterly performance exceeded expectations.</p>
        </body></html>
        """
        result = self.parser.get_mda(html, "10-Q")
        
        assert result is not None
        assert "Quarterly performance" in result
    
    def test_get_mda_not_found(self):
        """Test get_mda when section not found."""
        html = "<html><body><p>No MD&A section.</p></body></html>"
        result = self.parser.get_mda(html, "10-K")
        
        assert result is None


class TestParsedSection:
    """Tests for ParsedSection dataclass."""
    
    def test_parsed_section_creation(self):
        """Test creating a ParsedSection."""
        section = ParsedSection(
            name="1A",
            title="Risk Factors",
            content="Risk content here.",
            start_index=100,
            end_index=500
        )
        
        assert section.name == "1A"
        assert section.title == "Risk Factors"
        assert section.content == "Risk content here."
        assert section.start_index == 100
        assert section.end_index == 500


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def setup_method(self):
        """Set up parser instance for each test."""
        self.parser = SECFilingParser()
    
    def test_malformed_html(self):
        """Test handling of malformed HTML."""
        html = """
        <html><body>
            <p>Unclosed paragraph
            <div>Nested <span>content</div></span>
            <h2>ITEM 1A. RISK FACTORS</h2>
            <p>Risk content.</p>
        </body>
        """
        # Should not raise an exception
        result = self.parser.parse_10k(html)
        
        # BeautifulSoup should handle malformed HTML gracefully
        assert isinstance(result, dict)
    
    def test_missing_sections(self):
        """Test handling when expected sections are missing."""
        html = """
        <html><body>
            <h2>ITEM 1. BUSINESS</h2>
            <p>Business description only, no risk factors.</p>
        </body></html>
        """
        result = self.parser.parse_10k(html)
        
        # Should return dict, possibly with Item 1 but not 1A
        assert isinstance(result, dict)
        assert "1A" not in result or result.get("1A") is None
    
    def test_duplicate_section_headers(self):
        """Test handling of duplicate section headers (e.g., in table of contents)."""
        html = """
        <html><body>
            <!-- Table of Contents -->
            <p>ITEM 1A. RISK FACTORS.....page 10</p>
            <p>ITEM 7. MD&A.....page 25</p>
            
            <!-- Actual Content -->
            <h2>ITEM 1A. RISK FACTORS</h2>
            <p>This is the actual risk factors content with substantial detail 
            about the various risks facing the company including operational, 
            financial, and regulatory risks.</p>
            
            <h2>ITEM 7. MANAGEMENT'S DISCUSSION</h2>
            <p>Detailed MD&A content.</p>
        </body></html>
        """
        result = self.parser.parse_10k(html)
        
        # Should extract the actual content, not the TOC reference
        if "1A" in result:
            assert "actual risk factors content" in result["1A"].content or len(result["1A"].content) > 50
    
    def test_special_characters_in_content(self):
        """Test handling of special characters."""
        html = """
        <html><body>
            <h2>ITEM 1A. RISK FACTORS</h2>
            <p>Revenue was $1.5 billion (a 25% increase).</p>
            <p>Risk includes exposure to EUR/USD & GBP/USD rates.</p>
        </body></html>
        """
        result = self.parser.parse_10k(html)
        
        assert "1A" in result
        assert "$1.5 billion" in result["1A"].content
        assert "EUR/USD" in result["1A"].content
    
    def test_unicode_content(self):
        """Test handling of unicode characters."""
        html = """
        <html><body>
            <h2>ITEM 1A. RISK FACTORS</h2>
            <p>International operations in Europe and Asia.</p>
        </body></html>
        """
        result = self.parser.parse_10k(html)
        
        assert "1A" in result
        assert "International operations" in result["1A"].content
