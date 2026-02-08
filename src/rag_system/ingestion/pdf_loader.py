from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class DocumentMetadata:
    """Metadata for a document."""
    filename: str
    page_count: int
    file_path: str
    file_size_mb: float
    has_tables: bool
    has_images: bool


@dataclass
class DocumentContent:
    """Processed document content."""
    filename: str
    markdown: str
    json_structure: Dict[Any, Any]
    metadata: DocumentMetadata
    tables: List[Dict[Any, Any]]
    page_contents: List[Dict[str, Any]]


class DoclingPDFLoader:
    """Load and extract structured content from PDF documents using Docling."""
    
    def __init__(self, pdf_path: Path, extract_tables: bool = True, extract_images: bool = False):
        """Initialize Docling PDF loader.
        
        Args:
            pdf_path: Path to the PDF file
            extract_tables: Whether to extract tables
            extract_images: Whether to extract images
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.extract_tables = extract_tables
        self.extract_images = extract_images
        
        # Configure Docling pipeline
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_table_structure = extract_tables
        pipeline_options.do_ocr = False  # Set to True if you have scanned PDFs
        
        # Initialize converter
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        logger.info(f"Initialized Docling loader for: {self.pdf_path.name}")
    
    def extract_content(self) -> DocumentContent:
            """Extract structured content from PDF.
            
            Returns:
                DocumentContent object with all extracted information
            """
            try:
                logger.info(f"Converting {self.pdf_path.name} with Docling...")
                
                # Convert document
                result = self.converter.convert(str(self.pdf_path))
                
                # Export to different formats
                markdown_content = result.document.export_to_markdown()
                json_structure = result.document.export_to_dict()
                
                # Extract tables if available
                tables = []
                if self.extract_tables:
                    try:
                        for table in result.document.tables:
                            tables.append({
                                "data": table.export_to_dataframe(result.document).to_dict() if hasattr(table, 'export_to_dataframe') else {},
                                "caption": getattr(table, 'caption', ''),
                                "page": getattr(table, 'page', None)
                            })
                    except Exception as e:
                        logger.warning(f"Could not extract tables: {e}")
                
                # Extract page-level content
                page_contents = []
                try:
                    if hasattr(result.document, 'pages'):
                        for idx, page in enumerate(result.document.pages):
                            page_contents.append({
                                "page_number": idx + 1,  # Use index instead of page.page_no
                                "text": page.export_to_markdown() if hasattr(page, 'export_to_markdown') else str(page),
                                "size": getattr(page, 'size', None)
                            })
                except Exception as e:
                    logger.warning(f"Could not extract page contents: {e}")
                
                # Get metadata
                metadata = self.get_metadata()
                metadata.has_tables = len(tables) > 0
                
                content = DocumentContent(
                    filename=self.pdf_path.name,
                    markdown=markdown_content,
                    json_structure=json_structure,
                    metadata=metadata,
                    tables=tables,
                    page_contents=page_contents
                )
                
                logger.info(f"Successfully extracted content from {self.pdf_path.name}")
                logger.info(f"  - Pages: {len(page_contents)}")
                logger.info(f"  - Tables: {len(tables)}")
                logger.info(f"  - Markdown length: {len(markdown_content)} chars")
                
                return content
                
            except Exception as e:
                logger.error(f"Error extracting content from {self.pdf_path}: {e}")
                raise
    
    def get_metadata(self) -> DocumentMetadata:
        """Get metadata about the PDF document.
        
        Returns:
            DocumentMetadata object
        """
        try:
            # Basic file metadata
            file_size_mb = self.pdf_path.stat().st_size / (1024 * 1024)
            
            # Quick conversion to get page count
            result = self.converter.convert(str(self.pdf_path))
            page_count = len(result.document.pages) if hasattr(result.document, 'pages') else 0
            
            metadata = DocumentMetadata(
                filename=self.pdf_path.name,
                page_count=page_count,
                file_path=str(self.pdf_path),
                file_size_mb=round(file_size_mb, 2),
                has_tables=False,  # Will be updated during extraction
                has_images=False
            )
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting metadata from {self.pdf_path}: {e}")
            raise


class DoclingBatchLoader:
    """Load multiple PDF documents using Docling."""
    
    def __init__(self, pdf_directory: Path, extract_tables: bool = True, extract_images: bool = False):
        """Initialize batch loader.
        
        Args:
            pdf_directory: Directory containing PDF files
            extract_tables: Whether to extract tables
            extract_images: Whether to extract images
        """
        self.pdf_directory = Path(pdf_directory)
        if not self.pdf_directory.exists():
            raise FileNotFoundError(f"Directory not found: {pdf_directory}")
        
        self.extract_tables = extract_tables
        self.extract_images = extract_images
        
        self.pdf_files = list(self.pdf_directory.glob("*.pdf"))
        logger.info(f"Found {len(self.pdf_files)} PDF files in {pdf_directory}")
    
    def load_all(self) -> Dict[str, DocumentContent]:
        """Load all PDF files in the directory.
        
        Returns:
            Dictionary mapping filename to DocumentContent objects
        """
        all_documents = {}
        
        for pdf_path in self.pdf_files:
            try:
                loader = DoclingPDFLoader(
                    pdf_path, 
                    extract_tables=self.extract_tables,
                    extract_images=self.extract_images
                )
                content = loader.extract_content()
                all_documents[pdf_path.name] = content
                logger.info(f"✓ Loaded {pdf_path.name}")
            except Exception as e:
                logger.error(f"✗ Failed to load {pdf_path.name}: {e}")
                continue
        
        return all_documents
    
    def get_all_metadata(self) -> List[DocumentMetadata]:
        """Get metadata for all PDF files.
        
        Returns:
            List of DocumentMetadata objects
        """
        metadata_list = []
        
        for pdf_path in self.pdf_files:
            try:
                loader = DoclingPDFLoader(pdf_path)
                metadata = loader.get_metadata()
                metadata_list.append(metadata)
            except Exception as e:
                logger.error(f"Failed to get metadata for {pdf_path.name}: {e}")
                continue
        
        return metadata_list