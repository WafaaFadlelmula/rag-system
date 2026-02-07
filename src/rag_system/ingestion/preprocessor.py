import re
from typing import List
from dataclasses import dataclass

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class CleanedMarkdown:
    """Cleaned markdown with metadata."""
    original_length: int
    cleaned_length: int
    text: str
    preserved_structure: bool


class MarkdownPreprocessor:
    """Clean and normalize Docling markdown output."""
    
    def __init__(self, 
                 remove_extra_whitespace: bool = True,
                 preserve_headers: bool = True,
                 preserve_lists: bool = True,
                 preserve_tables: bool = True,
                 min_text_length: int = 10):
        """Initialize preprocessor with configuration.
        
        Args:
            remove_extra_whitespace: Remove excessive spaces and newlines
            preserve_headers: Keep markdown headers (# ## ###)
            preserve_lists: Keep markdown lists (- * 1.)
            preserve_tables: Keep markdown tables
            min_text_length: Minimum length for valid text
        """
        self.remove_extra_whitespace = remove_extra_whitespace
        self.preserve_headers = preserve_headers
        self.preserve_lists = preserve_lists
        self.preserve_tables = preserve_tables
        self.min_text_length = min_text_length
    
    def clean(self, markdown_text: str) -> CleanedMarkdown:
        """Clean and normalize markdown text.
        
        Args:
            markdown_text: Raw markdown text from Docling
            
        Returns:
            CleanedMarkdown object with cleaned text and metadata
        """
        original_length = len(markdown_text)
        cleaned = markdown_text
        
        # Remove excessive blank lines (more than 2 consecutive)
        if self.remove_extra_whitespace:
            cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
            # Remove trailing whitespace from lines
            cleaned = re.sub(r'[ \t]+$', '', cleaned, flags=re.MULTILINE)
            # Clean up spaces around headers
            cleaned = re.sub(r'\n\s*(#{1,6})\s+', r'\n\1 ', cleaned)
        
        # Remove page markers or other Docling artifacts if present
        cleaned = re.sub(r'<!-- PageBreak -->', '', cleaned)
        cleaned = re.sub(r'\[Page \d+\]', '', cleaned)
        
        # Remove isolated numbers (potential page numbers) but preserve numbered lists
        if not self.preserve_lists:
            cleaned = re.sub(r'^\s*\d+\s*$', '', cleaned, flags=re.MULTILINE)
        
        # Final cleanup
        cleaned = cleaned.strip()
        
        cleaned_length = len(cleaned)
        
        logger.debug(f"Cleaned markdown: {original_length} -> {cleaned_length} chars")
        
        return CleanedMarkdown(
            original_length=original_length,
            cleaned_length=cleaned_length,
            text=cleaned,
            preserved_structure=self.preserve_headers and self.preserve_lists
        )
    
    def is_valid_text(self, text: str) -> bool:
        """Check if text meets minimum quality criteria.
        
        Args:
            text: Text to validate
            
        Returns:
            True if text is valid, False otherwise
        """
        if len(text) < self.min_text_length:
            return False
        
        # Check if text has actual content (not just markdown formatting)
        text_without_markdown = re.sub(r'[#\*\-\[\]\(\)]+', '', text)
        if not re.search(r'[a-zA-Z]', text_without_markdown):
            return False
        
        return True
    
    def extract_sections(self, markdown_text: str) -> List[dict]:
        """Extract document sections based on headers.
        
        Args:
            markdown_text: Markdown text with headers
            
        Returns:
            List of sections with headers and content
        """
        sections = []
        lines = markdown_text.split('\n')
        
        current_section = {
            "header": "Introduction",
            "level": 0,
            "content": []
        }
        
        for line in lines:
            # Check if line is a header
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                # Save previous section if it has content
                if current_section["content"]:
                    current_section["content"] = '\n'.join(current_section["content"])
                    sections.append(current_section)
                
                # Start new section
                level = len(header_match.group(1))
                header_text = header_match.group(2)
                current_section = {
                    "header": header_text,
                    "level": level,
                    "content": []
                }
            else:
                current_section["content"].append(line)
        
        # Add the last section
        if current_section["content"]:
            current_section["content"] = '\n'.join(current_section["content"])
            sections.append(current_section)
        
        logger.debug(f"Extracted {len(sections)} sections from markdown")
        return sections