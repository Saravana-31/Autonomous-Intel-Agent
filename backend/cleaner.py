"""HTML cleaning utilities for extracting readable text."""

import re
from typing import List, Tuple
from bs4 import BeautifulSoup


class HTMLCleaner:
    """Cleans HTML content and extracts readable text."""
    
    REMOVE_TAGS = [
        "script", "style", "nav", "footer", "header", 
        "aside", "iframe", "noscript", "svg", "canvas",
        "form", "button", "input", "select", "textarea"
    ]
    
    REMOVE_CLASSES = [
        "nav", "navbar", "navigation", "menu", "sidebar",
        "footer", "header", "cookie", "popup", "modal",
        "advertisement", "ad", "social", "share"
    ]
    
    def clean_html(self, html: str) -> str:
        """
        Clean HTML and extract readable text.
        
        Args:
            html: Raw HTML content
            
        Returns:
            Cleaned text content
        """
        soup = BeautifulSoup(html, "lxml")
        
        # Remove unwanted tags
        for tag in self.REMOVE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Remove elements with navigation/footer classes
        for class_pattern in self.REMOVE_CLASSES:
            for element in soup.find_all(class_=re.compile(class_pattern, re.I)):
                element.decompose()
            for element in soup.find_all(id=re.compile(class_pattern, re.I)):
                element.decompose()
        
        # Extract text
        text = soup.get_text(separator="\n", strip=True)
        
        # Clean up whitespace
        text = self._clean_whitespace(text)
        
        return text
    
    def _clean_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        # Replace multiple newlines with double newline
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Replace multiple spaces with single space
        text = re.sub(r" {2,}", " ", text)
        # Strip lines
        lines = [line.strip() for line in text.split("\n")]
        # Remove empty lines
        lines = [line for line in lines if line]
        return "\n".join(lines)
    
    def process_files(self, files: List[Tuple[str, str]]) -> str:
        """
        Process multiple HTML files and concatenate text.
        
        Args:
            files: List of (filename, content) tuples
            
        Returns:
            Concatenated cleaned text
        """
        cleaned_texts = []
        
        for filename, content in files:
            cleaned = self.clean_html(content)
            if cleaned:
                cleaned_texts.append(f"--- {filename} ---\n{cleaned}")
        
        return "\n\n".join(cleaned_texts)
    
    def truncate_text(self, text: str, max_chars: int = 3000) -> str:
        """
        Truncate text to fit within token limits.
        
        Args:
            text: Input text
            max_chars: Maximum character count
            
        Returns:
            Truncated text
        """
        if len(text) <= max_chars:
            return text
        
        # Try to cut at sentence boundary
        truncated = text[:max_chars]
        last_period = truncated.rfind(".")
        
        if last_period > max_chars * 0.7:
            return truncated[:last_period + 1]
        
        return truncated + "..."
