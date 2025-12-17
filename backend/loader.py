"""HTML file loader for offline website snapshots."""

import os
from pathlib import Path
from typing import List, Tuple


class HTMLLoader:
    """Loads HTML files from company data directories."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
    
    def get_company_path(self, company: str) -> Path:
        """Get the path to a company's data directory."""
        return self.data_dir / company
    
    def list_companies(self) -> List[str]:
        """List all available company directories."""
        if not self.data_dir.exists():
            return []
        return [d.name for d in self.data_dir.iterdir() if d.is_dir()]
    
    def load_html_files(self, company: str) -> List[Tuple[str, str]]:
        """
        Load all HTML files for a company.
        
        Returns:
            List of tuples (filename, content)
        """
        company_path = self.get_company_path(company)
        
        if not company_path.exists():
            raise FileNotFoundError(f"Company directory not found: {company_path}")
        
        html_files = []
        
        for html_file in company_path.glob("*.html"):
            try:
                with open(html_file, "r", encoding="utf-8") as f:
                    content = f.read()
                html_files.append((html_file.name, content))
            except Exception as e:
                print(f"Error reading {html_file}: {e}")
                continue
        
        if not html_files:
            raise ValueError(f"No HTML files found in {company_path}")
        
        return html_files
    
    def company_exists(self, company: str) -> bool:
        """Check if a company directory exists."""
        return self.get_company_path(company).exists()
