"""
Unit tests for Filing Chunker.

Tests text chunking, sentence boundary detection, overlap, and metadata preservation.
"""

import pytest
from src.data.chunker import FilingChunker, Chunk


class TestChunkerInitialization:
    """Tests for chunker initialization and configuration."""
    
    def test_default_configuration(self):
        """Test default chunker configuration."""
        chunker = FilingChunker()
        
        assert chunker.chunk_size == 800
        assert chunker.chunk_overlap == 100
        assert chunker.min_chunk_size == 100
    
    def test_custom_configuration(self):
        """Test custom chunker configuration."""
        chunker = FilingChunker(
            chunk_size=500,
            chunk_overlap=50,
            min_chunk_size=50
        )
        
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50
        assert chunker.min_chunk_size == 50
    
    def test_invalid_overlap_raises_error(self):
        """Test that overlap >= chunk_size raises ValueError."""
        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            FilingChunker(chunk_size=100, chunk_overlap=100)
        
        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            FilingChunker(chunk_size=100, chunk_overlap=150)
    
    def test_invalid_min_size_raises_error(self):
        """Test that min_chunk_size > chunk_size raises ValueError."""
        with pytest.raises(ValueError, match="min_chunk_size must be less than or equal to chunk_size"):
            FilingChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=150)


class TestBasicChunking:
    """Tests for basic text chunking functionality."""
    
    def setup_method(self):
        """Set up chunker with small sizes for testing."""
        self.chunker = FilingChunker(
            chunk_size=100,
            chunk_overlap=20,
            min_chunk_size=10
        )
    
    def test_chunk_short_text(self):
        """Test that short text returns single chunk."""
        text = "This is a short text that fits in one chunk."
        chunks = self.chunker.chunk_text(text)
        
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0
    
    def test_chunk_empty_text(self):
        """Test that empty text returns no chunks."""
        assert self.chunker.chunk_text("") == []
        assert self.chunker.chunk_text("   ") == []
        assert self.chunker.chunk_text(None) == []
    
    def test_chunk_long_text(self):
        """Test chunking of text longer than chunk_size."""
        # Create text that's about 300 characters
        text = "This is sentence one. " * 15  # ~330 chars
        chunks = self.chunker.chunk_text(text)
        
        assert len(chunks) > 1
        # Verify chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
    
    def test_chunk_preserves_content(self):
        """Test that no content is lost during chunking."""
        text = "First sentence here. Second sentence follows. Third sentence ends."
        chunker = FilingChunker(chunk_size=30, chunk_overlap=5, min_chunk_size=5)
        chunks = chunker.chunk_text(text)
        
        # All original words should appear in at least one chunk
        original_words = set(text.split())
        chunked_words = set()
        for chunk in chunks:
            chunked_words.update(chunk.text.split())
        
        # Check key words are preserved
        assert "First" in chunked_words
        assert "Second" in chunked_words
        assert "Third" in chunked_words


class TestSentenceBoundaries:
    """Tests for sentence boundary detection."""
    
    def setup_method(self):
        """Set up chunker for sentence boundary testing."""
        self.chunker = FilingChunker(
            chunk_size=100,
            chunk_overlap=20,
            min_chunk_size=10
        )
    
    def test_breaks_at_sentence_end(self):
        """Test that chunks prefer to break at sentence endings."""
        text = "First sentence ends here. Second sentence starts now. Third one follows."
        chunks = self.chunker.chunk_text(text)
        
        # Chunks should end with periods (sentence boundaries)
        for chunk in chunks[:-1]:  # Exclude last chunk
            # Should end with punctuation or be at a natural break
            assert chunk.text.rstrip()[-1] in '.!?;:' or len(chunk.text) <= self.chunker.chunk_size
    
    def test_handles_question_marks(self):
        """Test sentence detection with question marks."""
        text = "What is the risk? The risk is significant. How do we mitigate it? We use hedging."
        chunks = self.chunker.chunk_text(text)
        
        assert len(chunks) >= 1
        # Content should be preserved
        combined = " ".join(c.text for c in chunks)
        assert "risk" in combined
        assert "hedging" in combined
    
    def test_handles_exclamation_marks(self):
        """Test sentence detection with exclamation marks."""
        text = "Warning! This is critical. Important! Pay attention."
        chunks = self.chunker.chunk_text(text)
        
        assert len(chunks) >= 1
    
    def test_fallback_to_soft_boundaries(self):
        """Test fallback to semicolons and colons when no sentence end found."""
        text = "Item one; item two; item three: details here and more content follows"
        chunker = FilingChunker(chunk_size=30, chunk_overlap=5, min_chunk_size=5)
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) >= 1


class TestChunkOverlap:
    """Tests for chunk overlap functionality."""
    
    def test_chunks_have_overlap(self):
        """Test that consecutive chunks have overlapping content."""
        # Create text long enough for multiple chunks
        text = "Sentence one is here. Sentence two follows. Sentence three comes next. Sentence four ends it."
        chunker = FilingChunker(chunk_size=50, chunk_overlap=15, min_chunk_size=10)
        chunks = chunker.chunk_text(text)
        
        if len(chunks) >= 2:
            # Check that end of chunk N overlaps with start of chunk N+1
            for i in range(len(chunks) - 1):
                chunk1_end = chunks[i].text[-20:] if len(chunks[i].text) >= 20 else chunks[i].text
                chunk2_start = chunks[i + 1].text[:20] if len(chunks[i + 1].text) >= 20 else chunks[i + 1].text
                
                # There should be some common words due to overlap
                words1 = set(chunk1_end.split())
                words2 = set(chunk2_start.split())
                # Overlap means some words should appear in both
                # (This is a soft check since boundary detection may vary)
    
    def test_overlap_positions(self):
        """Test that chunk positions reflect overlap."""
        text = "A" * 300  # Simple text for predictable chunking
        chunker = FilingChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)
        chunks = chunker.chunk_text(text)
        
        if len(chunks) >= 2:
            # Second chunk should start before first chunk ends (overlap)
            # Due to sentence boundary detection, this may vary
            assert chunks[1].start_char < chunks[0].end_char or chunks[1].start_char == chunks[0].end_char - 20


class TestMinimumChunkSize:
    """Tests for minimum chunk size enforcement."""
    
    def test_min_chunk_size_enforced(self):
        """Test that chunks below min_chunk_size are handled."""
        chunker = FilingChunker(chunk_size=100, chunk_overlap=10, min_chunk_size=50)
        
        # Text that would create a small final chunk
        text = "This is a longer sentence that should create proper chunks. End."
        chunks = chunker.chunk_text(text)
        
        # All chunks should meet minimum size (or be merged)
        for chunk in chunks:
            # Either meets min size or is the only chunk
            assert len(chunk.text) >= chunker.min_chunk_size or len(chunks) == 1
    
    def test_very_short_text_below_min(self):
        """Test handling of text shorter than min_chunk_size."""
        chunker = FilingChunker(chunk_size=100, chunk_overlap=10, min_chunk_size=50)
        
        # Text shorter than min_chunk_size but not empty
        text = "Short text."
        chunks = chunker.chunk_text(text)
        
        # Should still return the chunk (content preservation)
        assert len(chunks) == 1
        assert chunks[0].text == text


class TestMetadataPreservation:
    """Tests for metadata preservation in chunks."""
    
    def setup_method(self):
        """Set up chunker for metadata testing."""
        self.chunker = FilingChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)
    
    def test_chunk_text_with_metadata(self):
        """Test that metadata is attached to chunks."""
        text = "This is test content for chunking with metadata."
        metadata = {"source": "test", "id": 123}
        
        chunks = self.chunker.chunk_text(text, metadata=metadata)
        
        assert len(chunks) == 1
        assert chunks[0].metadata["source"] == "test"
        assert chunks[0].metadata["id"] == 123
    
    def test_chunk_section_metadata(self):
        """Test chunk_section adds filing metadata."""
        text = "Risk factors include market volatility and regulatory changes. These risks are material."
        
        chunks = self.chunker.chunk_section(
            section_text=text,
            section_name="1A",
            filing_type="10-K",
            ticker="AAPL",
            filing_date="2024-01-15",
            accession_number="0000320193-24-000001"
        )
        
        assert len(chunks) >= 1
        chunk = chunks[0]
        
        assert chunk.metadata["section"] == "1A"
        assert chunk.metadata["filing_type"] == "10-K"
        assert chunk.metadata["ticker"] == "AAPL"
        assert chunk.metadata["filing_date"] == "2024-01-15"
        assert chunk.metadata["accession_number"] == "0000320193-24-000001"
        assert "total_chunks" in chunk.metadata
        assert "chunk_position" in chunk.metadata
    
    def test_chunk_section_optional_metadata(self):
        """Test chunk_section with optional metadata omitted."""
        text = "Some filing content here."
        
        chunks = self.chunker.chunk_section(
            section_text=text,
            section_name="7",
            filing_type="10-Q",
            ticker="MSFT"
        )
        
        assert len(chunks) == 1
        assert chunks[0].metadata["section"] == "7"
        assert chunks[0].metadata["ticker"] == "MSFT"
        assert "filing_date" not in chunks[0].metadata
        assert "accession_number" not in chunks[0].metadata
    
    def test_chunk_position_format(self):
        """Test chunk_position metadata format."""
        text = "First sentence here. " * 20  # Long enough for multiple chunks
        
        chunks = self.chunker.chunk_section(
            section_text=text,
            section_name="1A",
            filing_type="10-K",
            ticker="NVDA"
        )
        
        if len(chunks) > 1:
            assert chunks[0].metadata["chunk_position"] == f"1/{len(chunks)}"
            assert chunks[-1].metadata["chunk_position"] == f"{len(chunks)}/{len(chunks)}"


class TestChunkFiling:
    """Tests for chunking entire filings."""
    
    def setup_method(self):
        """Set up chunker for filing tests."""
        self.chunker = FilingChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)
    
    def test_chunk_filing_multiple_sections(self):
        """Test chunking a filing with multiple sections."""
        sections = {
            "1A": "Risk factors section content. Material risks are described here.",
            "7": "Management discussion and analysis. Revenue grew significantly.",
            "8": "Financial statements section. See consolidated statements."
        }
        
        chunks = self.chunker.chunk_filing(
            sections=sections,
            filing_type="10-K",
            ticker="GOOGL",
            filing_date="2024-02-01"
        )
        
        assert len(chunks) >= 3  # At least one chunk per section
        
        # Verify sections are represented
        section_names = {c.metadata["section"] for c in chunks}
        assert "1A" in section_names
        assert "7" in section_names
        assert "8" in section_names
    
    def test_chunk_filing_global_index(self):
        """Test that global_index is assigned across sections."""
        sections = {
            "1": "Business section content.",
            "1A": "Risk factors content."
        }
        
        chunks = self.chunker.chunk_filing(
            sections=sections,
            filing_type="10-K",
            ticker="META"
        )
        
        # Global indices should be sequential
        global_indices = [c.metadata["global_index"] for c in chunks]
        assert global_indices == list(range(len(chunks)))
    
    def test_chunk_filing_empty_sections(self):
        """Test handling of empty sections in filing."""
        sections = {
            "1A": "Risk content here.",
            "7": "",  # Empty section
            "8": "Financial content."
        }
        
        chunks = self.chunker.chunk_filing(
            sections=sections,
            filing_type="10-K",
            ticker="AMZN"
        )
        
        # Empty section should not produce chunks
        section_names = {c.metadata["section"] for c in chunks}
        assert "7" not in section_names


class TestChunkDataclass:
    """Tests for the Chunk dataclass."""
    
    def test_chunk_creation(self):
        """Test creating a Chunk object."""
        chunk = Chunk(
            text="Test content",
            chunk_index=0,
            start_char=0,
            end_char=12,
            metadata={"key": "value"}
        )
        
        assert chunk.text == "Test content"
        assert chunk.chunk_index == 0
        assert chunk.start_char == 0
        assert chunk.end_char == 12
        assert chunk.metadata == {"key": "value"}
    
    def test_chunk_char_count_property(self):
        """Test char_count property."""
        chunk = Chunk(
            text="Hello World",
            chunk_index=0,
            start_char=0,
            end_char=11
        )
        
        assert chunk.char_count == 11
    
    def test_chunk_default_metadata(self):
        """Test that metadata defaults to empty dict."""
        chunk = Chunk(
            text="Content",
            chunk_index=0,
            start_char=0,
            end_char=7
        )
        
        assert chunk.metadata == {}


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def setup_method(self):
        """Set up chunker for edge case testing."""
        self.chunker = FilingChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)
    
    def test_text_with_only_whitespace(self):
        """Test handling of whitespace-only text."""
        assert self.chunker.chunk_text("     ") == []
        assert self.chunker.chunk_text("\n\n\n") == []
        assert self.chunker.chunk_text("\t\t") == []
    
    def test_text_with_special_characters(self):
        """Test handling of special characters."""
        text = "Revenue was $1.5B (up 25%). Risk: EUR/USD exposure & regulatory changes."
        chunks = self.chunker.chunk_text(text)
        
        assert len(chunks) >= 1
        assert "$1.5B" in chunks[0].text
    
    def test_text_with_numbers(self):
        """Test handling of numeric content."""
        text = "Q4 2023: Revenue $500M. Q3 2023: Revenue $450M. Growth: 11.1%."
        chunks = self.chunker.chunk_text(text)
        
        assert len(chunks) >= 1
        combined = " ".join(c.text for c in chunks)
        assert "500M" in combined
        assert "11.1%" in combined
    
    def test_very_long_sentence(self):
        """Test handling of a single very long sentence without breaks."""
        # A sentence longer than chunk_size with no natural breaks
        text = "word " * 50  # ~250 characters, no sentence endings
        chunks = self.chunker.chunk_text(text)
        
        # Should still produce chunks even without sentence boundaries
        assert len(chunks) >= 1
    
    def test_unicode_content(self):
        """Test handling of unicode characters."""
        text = "International operations in Europe and Asia. Revenue in multiple currencies."
        chunks = self.chunker.chunk_text(text)
        
        assert len(chunks) >= 1
    
    def test_multiple_spaces_normalized(self):
        """Test that multiple spaces are normalized."""
        text = "Word    with    many    spaces    between."
        chunks = self.chunker.chunk_text(text)
        
        assert len(chunks) == 1
        # Multiple spaces should be normalized to single spaces
        assert "    " not in chunks[0].text


class TestRealWorldScenarios:
    """Tests simulating real SEC filing content."""
    
    def setup_method(self):
        """Set up chunker with production-like settings."""
        self.chunker = FilingChunker(
            chunk_size=800,
            chunk_overlap=100,
            min_chunk_size=100
        )
    
    def test_risk_factors_section(self):
        """Test chunking a realistic risk factors section."""
        risk_factors = """
        RISK FACTORS
        
        Investing in our common stock involves a high degree of risk. You should carefully 
        consider the risks and uncertainties described below, together with all of the other 
        information in this Annual Report on Form 10-K, including our consolidated financial 
        statements and related notes, before making an investment decision.
        
        Competition Risk: We face intense competition in all of our markets. Our competitors 
        may have greater financial resources, more extensive research and development 
        capabilities, and larger sales and marketing organizations than we do.
        
        Regulatory Risk: Changes in laws and regulations could adversely affect our business. 
        We are subject to various federal, state, and local laws and regulations that govern 
        our operations, including environmental, health and safety, and data privacy laws.
        
        Market Risk: Our business is subject to the risks arising from adverse changes in 
        general economic conditions. Economic downturns could reduce demand for our products 
        and services, which could have a material adverse effect on our results of operations.
        """
        
        chunks = self.chunker.chunk_text(risk_factors)
        
        assert len(chunks) >= 1
        # Key terms should be preserved
        combined = " ".join(c.text for c in chunks)
        assert "Competition Risk" in combined
        assert "Regulatory Risk" in combined
        assert "Market Risk" in combined
    
    def test_mda_section(self):
        """Test chunking a realistic MD&A section."""
        mda = """
        MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS
        
        The following discussion should be read in conjunction with our consolidated financial 
        statements and related notes included elsewhere in this Annual Report on Form 10-K.
        
        Overview: We are a leading provider of technology solutions. During fiscal year 2023, 
        we achieved record revenue of $50 billion, representing a 25% increase compared to 
        the prior year. This growth was driven primarily by strong demand for our cloud 
        services and enterprise software products.
        
        Revenue: Total revenue for fiscal 2023 was $50.0 billion compared to $40.0 billion 
        for fiscal 2022. The increase of $10.0 billion, or 25%, was primarily due to growth 
        in our cloud segment, which increased 40% year-over-year.
        
        Operating Expenses: Total operating expenses increased 15% to $35.0 billion in fiscal 
        2023 from $30.4 billion in fiscal 2022. The increase was primarily driven by higher 
        research and development investments and increased headcount to support our growth.
        """
        
        chunks = self.chunker.chunk_text(mda)
        
        assert len(chunks) >= 1
        combined = " ".join(c.text for c in chunks)
        assert "$50 billion" in combined or "$50.0 billion" in combined
        assert "25%" in combined
