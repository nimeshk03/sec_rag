"""
Text Chunker Module

Splits SEC filing sections into semantically meaningful chunks for embedding.
Preserves metadata and respects sentence boundaries.
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def char_count(self) -> int:
        """Return the character count of the chunk text."""
        return len(self.text)


class FilingChunker:
    """
    Splits SEC filing text into overlapping chunks for embedding.
    
    Features:
    - Configurable chunk size and overlap
    - Sentence-boundary detection
    - Metadata preservation
    - Minimum chunk size enforcement
    """
    
    # Sentence-ending patterns
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
    
    # Alternative sentence boundaries (for edge cases)
    SOFT_BOUNDARIES = re.compile(r'(?<=[;:])\s+')
    
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        min_chunk_size: int = 100
    ):
        """
        Initialize the chunker with configuration.
        
        Args:
            chunk_size: Target size for each chunk in characters (default: 800)
            chunk_overlap: Number of overlapping characters between chunks (default: 100)
            min_chunk_size: Minimum chunk size to emit (default: 100)
        """
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if min_chunk_size > chunk_size:
            raise ValueError("min_chunk_size must be less than or equal to chunk_size")
        
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def _find_sentence_boundary(self, text: str, target_pos: int, search_range: int = 100) -> int:
        """
        Find the nearest sentence boundary to the target position.
        
        Searches within search_range characters before target_pos for a sentence ending.
        Falls back to soft boundaries (semicolons, colons) if no sentence ending found.
        
        Args:
            text: The text to search in
            target_pos: Target position to find boundary near
            search_range: How far back to search for a boundary
            
        Returns:
            Position of the best boundary found, or target_pos if none found
        """
        if target_pos >= len(text):
            return len(text)
        
        # Search window: from (target_pos - search_range) to target_pos
        search_start = max(0, target_pos - search_range)
        search_text = text[search_start:target_pos]
        
        # Look for sentence endings (. ! ?) followed by space and capital letter
        # We need to find the last one in the search window
        best_boundary = None
        
        # Find all sentence endings in the search window
        for match in self.SENTENCE_ENDINGS.finditer(search_text):
            best_boundary = search_start + match.start() + 1  # Position after the punctuation
        
        if best_boundary is not None:
            return best_boundary
        
        # Fall back to soft boundaries (semicolons, colons)
        for match in self.SOFT_BOUNDARIES.finditer(search_text):
            best_boundary = search_start + match.start() + 1
        
        if best_boundary is not None:
            return best_boundary
        
        # No boundary found, use target position
        return target_pos
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences for analysis.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        # Split on sentence endings
        sentences = self.SENTENCE_ENDINGS.split(text)
        
        # Clean up and filter empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Split text into overlapping chunks respecting sentence boundaries.
        
        Args:
            text: Text content to chunk
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of Chunk objects with text and metadata
        """
        if not text or not text.strip():
            return []
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        if len(text) <= self.chunk_size:
            # Text fits in a single chunk
            if len(text) >= self.min_chunk_size:
                return [Chunk(
                    text=text,
                    chunk_index=0,
                    start_char=0,
                    end_char=len(text),
                    metadata=dict(metadata) if metadata else {}
                )]
            else:
                # Text is too short, return empty or single chunk based on content
                if text.strip():
                    return [Chunk(
                        text=text,
                        chunk_index=0,
                        start_char=0,
                        end_char=len(text),
                        metadata=dict(metadata) if metadata else {}
                    )]
                return []
        
        chunks = []
        current_pos = 0
        chunk_index = 0
        
        while current_pos < len(text):
            # Calculate target end position
            target_end = current_pos + self.chunk_size
            
            if target_end >= len(text):
                # Last chunk - take everything remaining
                chunk_text = text[current_pos:].strip()
                if len(chunk_text) >= self.min_chunk_size:
                    chunks.append(Chunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        start_char=current_pos,
                        end_char=len(text),
                        metadata=dict(metadata) if metadata else {}
                    ))
                elif chunks and len(chunk_text) > 0:
                    # Merge with previous chunk if too small
                    prev_chunk = chunks[-1]
                    merged_text = prev_chunk.text + " " + chunk_text
                    chunks[-1] = Chunk(
                        text=merged_text,
                        chunk_index=prev_chunk.chunk_index,
                        start_char=prev_chunk.start_char,
                        end_char=len(text),
                        metadata=prev_chunk.metadata
                    )
                break
            
            # Find sentence boundary near target end
            actual_end = self._find_sentence_boundary(text, target_end)
            
            # Ensure we make progress
            if actual_end <= current_pos:
                actual_end = target_end
            
            # Extract chunk text
            chunk_text = text[current_pos:actual_end].strip()
            
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(Chunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    start_char=current_pos,
                    end_char=actual_end,
                    metadata=dict(metadata) if metadata else {}
                ))
                chunk_index += 1
                # Move to next position with overlap
                next_pos = actual_end - self.chunk_overlap
                # Ensure we don't go backwards
                if next_pos <= current_pos:
                    next_pos = actual_end
                current_pos = next_pos
            else:
                # Chunk too small, skip ahead without overlap
                current_pos = actual_end
        
        return chunks
    
    def chunk_section(
        self,
        section_text: str,
        section_name: str,
        filing_type: str,
        ticker: str,
        filing_date: Optional[str] = None,
        accession_number: Optional[str] = None
    ) -> List[Chunk]:
        """
        Chunk a filing section with full metadata.
        
        Args:
            section_text: Text content of the section
            section_name: Section identifier (e.g., "1A", "7")
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            ticker: Stock ticker symbol
            filing_date: Optional filing date
            accession_number: Optional SEC accession number
            
        Returns:
            List of Chunk objects with filing metadata
        """
        metadata = {
            "section": section_name,
            "filing_type": filing_type,
            "ticker": ticker,
        }
        
        if filing_date:
            metadata["filing_date"] = filing_date
        if accession_number:
            metadata["accession_number"] = accession_number
        
        chunks = self.chunk_text(section_text, metadata)
        
        # Add chunk-specific metadata
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk.metadata["total_chunks"] = total_chunks
            chunk.metadata["chunk_position"] = f"{chunk.chunk_index + 1}/{total_chunks}"
        
        return chunks
    
    def chunk_filing(
        self,
        sections: Dict[str, str],
        filing_type: str,
        ticker: str,
        filing_date: Optional[str] = None,
        accession_number: Optional[str] = None
    ) -> List[Chunk]:
        """
        Chunk all sections of a filing.
        
        Args:
            sections: Dict mapping section IDs to text content
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            ticker: Stock ticker symbol
            filing_date: Optional filing date
            accession_number: Optional SEC accession number
            
        Returns:
            List of all Chunk objects from all sections
        """
        all_chunks = []
        global_index = 0
        
        for section_name, section_text in sections.items():
            section_chunks = self.chunk_section(
                section_text=section_text,
                section_name=section_name,
                filing_type=filing_type,
                ticker=ticker,
                filing_date=filing_date,
                accession_number=accession_number
            )
            
            # Update global chunk indices
            for chunk in section_chunks:
                chunk.metadata["global_index"] = global_index
                global_index += 1
            
            all_chunks.extend(section_chunks)
        
        return all_chunks
    
    def get_overlap_text(self, chunk1: Chunk, chunk2: Chunk) -> Optional[str]:
        """
        Get the overlapping text between two consecutive chunks.
        
        Args:
            chunk1: First chunk
            chunk2: Second chunk (should follow chunk1)
            
        Returns:
            Overlapping text, or None if chunks don't overlap
        """
        if chunk2.start_char >= chunk1.end_char:
            return None
        
        # Calculate overlap region
        overlap_start = chunk2.start_char
        overlap_end = min(chunk1.end_char, chunk2.start_char + len(chunk2.text))
        
        # Extract from chunk2 (which contains the overlap at its start)
        overlap_length = chunk1.end_char - chunk2.start_char
        if overlap_length > 0 and overlap_length <= len(chunk2.text):
            return chunk2.text[:overlap_length]
        
        return None
