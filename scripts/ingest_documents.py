#!/usr/bin/env python3
"""
Script to ingest PDF documents using Docling and save processed content.
"""
import json
from pathlib import Path
from datetime import datetime

from rag_system.config.settings import settings
from rag_system.ingestion.pdf_loader import DoclingBatchLoader
from rag_system.ingestion.preprocessor import MarkdownPreprocessor
from rag_system.utils.logger import setup_logger

logger = setup_logger(__name__, settings.log_level)


def main():
    """Main ingestion pipeline with Docling."""
    logger.info("=" * 70)
    logger.info("Starting Docling Document Ingestion Pipeline")
    logger.info("=" * 70)
    
    # Initialize components
    batch_loader = DoclingBatchLoader(
        settings.raw_data_path,
        extract_tables=settings.export_tables,
        extract_images=settings.export_images
    )
    preprocessor = MarkdownPreprocessor()
    
    # Get metadata
    logger.info("\n--- Document Metadata ---")
    metadata_list = batch_loader.get_all_metadata()
    for metadata in metadata_list:
        logger.info(f"  {metadata.filename}: {metadata.page_count} pages, {metadata.file_size_mb} MB")
    
    # Load all documents
    logger.info("\n--- Loading Documents with Docling ---")
    all_documents = batch_loader.load_all()
    
    # Process and save
    logger.info("\n--- Processing Documents ---")
    processed_docs = {}
    stats = {
        "total_documents": len(all_documents),
        "total_pages": 0,
        "total_tables": 0,
        "total_chars_original": 0,
        "total_chars_cleaned": 0,
        "documents": {},
        "timestamp": datetime.now().isoformat()
    }
    
    for filename, doc_content in all_documents.items():
        logger.info(f"\nProcessing: {filename}")
        
        # Clean markdown
        cleaned = preprocessor.clean(doc_content.markdown)
        
        # Extract sections
        sections = preprocessor.extract_sections(cleaned.text)
        
        if preprocessor.is_valid_text(cleaned.text):
            processed_doc = {
                "filename": filename,
                "markdown": cleaned.text,
                "sections": sections,
                "metadata": {
                    "page_count": doc_content.metadata.page_count,
                    "file_size_mb": doc_content.metadata.file_size_mb,
                    "has_tables": doc_content.metadata.has_tables,
                    "original_length": cleaned.original_length,
                    "cleaned_length": cleaned.cleaned_length,
                },
                "tables": doc_content.tables,
                "page_contents": doc_content.page_contents
            }
            
            processed_docs[filename] = processed_doc
            
            # Update stats
            stats["total_pages"] += doc_content.metadata.page_count
            stats["total_tables"] += len(doc_content.tables)
            stats["total_chars_original"] += cleaned.original_length
            stats["total_chars_cleaned"] += cleaned.cleaned_length
            stats["documents"][filename] = {
                "pages": doc_content.metadata.page_count,
                "tables": len(doc_content.tables),
                "sections": len(sections),
                "chars": cleaned.cleaned_length
            }
            
            logger.info(f"  ✓ Pages: {doc_content.metadata.page_count}")
            logger.info(f"  ✓ Tables: {len(doc_content.tables)}")
            logger.info(f"  ✓ Sections: {len(sections)}")
            logger.info(f"  ✓ Content: {cleaned.cleaned_length:,} chars")
        else:
            logger.warning(f"  ✗ Skipped (insufficient content)")
    
    # Save processed documents
    logger.info("\n--- Saving Processed Documents ---")
    
    # Save full processed documents
    output_path = settings.processed_data_path / "processed_documents.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(processed_docs, f, indent=2, ensure_ascii=False)
    logger.info(f"✓ Saved to: {output_path}")
    
    # Save markdown versions separately for easy viewing
    markdown_dir = settings.processed_data_path / "markdown"
    markdown_dir.mkdir(exist_ok=True)
    for filename, doc in processed_docs.items():
        md_path = markdown_dir / f"{Path(filename).stem}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(doc["markdown"])
    logger.info(f"✓ Saved markdown files to: {markdown_dir}")
    
    # Save statistics
    stats_path = settings.processed_data_path / "ingestion_stats.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"✓ Statistics saved to: {stats_path}")
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Documents processed: {stats['total_documents']}")
    logger.info(f"Total pages: {stats['total_pages']}")
    logger.info(f"Total tables extracted: {stats['total_tables']}")
    logger.info(f"Total characters (original): {stats['total_chars_original']:,}")
    logger.info(f"Total characters (cleaned): {stats['total_chars_cleaned']:,}")
    logger.info(f"Reduction: {100 * (1 - stats['total_chars_cleaned'] / max(stats['total_chars_original'], 1)):.1f}%")
    logger.info("\nPer-document breakdown:")
    for fname, doc_stats in stats["documents"].items():
        logger.info(f"  {fname}:")
        logger.info(f"    - Pages: {doc_stats['pages']}, Tables: {doc_stats['tables']}, Sections: {doc_stats['sections']}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()