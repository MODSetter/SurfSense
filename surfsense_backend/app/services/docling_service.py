#!/usr/bin/env python3
"""
Docling Document Processing Service for SurfSense
SSL-safe implementation with pre-downloaded models
"""

import logging
import os
import ssl
from typing import Any

logger = logging.getLogger(__name__)


class DoclingService:
    """Docling service for enhanced document processing with SSL fixes."""

    def __init__(self):
        """Initialize Docling service with SSL, model fixes, and GPU acceleration."""
        self.converter = None
        self.use_gpu = False
        self._configure_ssl_environment()
        self._check_wsl2_gpu_support()
        self._initialize_docling()

    def _configure_ssl_environment(self):
        """Configure SSL environment for secure model downloads."""
        try:
            # Set SSL context for downloads
            ssl._create_default_https_context = ssl._create_unverified_context

            # Set SSL environment variables if not already set
            if not os.environ.get("SSL_CERT_FILE"):
                try:
                    import certifi

                    os.environ["SSL_CERT_FILE"] = certifi.where()
                    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
                except ImportError:
                    pass

            logger.info("🔐 SSL environment configured for model downloads")
        except Exception as e:
            logger.warning(f"⚠️ SSL configuration warning: {e}")

    def _check_wsl2_gpu_support(self):
        """Check and configure GPU support for WSL2 environment."""
        try:
            import torch

            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
                logger.info(f"✅ WSL2 GPU detected: {gpu_name} ({gpu_count} devices)")
                logger.info(f"🚀 CUDA Version: {torch.version.cuda}")
                self.use_gpu = True
            else:
                logger.info("⚠️ CUDA not available in WSL2, falling back to CPU")
                self.use_gpu = False
        except ImportError:
            logger.info("⚠️ PyTorch not found, falling back to CPU")
            self.use_gpu = False
        except Exception as e:
            logger.warning(f"⚠️ GPU detection failed: {e}, falling back to CPU")
            self.use_gpu = False

    def _initialize_docling(self):
        """Initialize Docling with version-safe configuration."""
        try:
            from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            logger.info("🔧 Initializing Docling with version-safe configuration...")

            # Create pipeline options with version-safe attribute checking
            pipeline_options = PdfPipelineOptions()

            # Disable OCR (user request)
            if hasattr(pipeline_options, "do_ocr"):
                pipeline_options.do_ocr = False
                logger.info("⚠️ OCR disabled by user request")
            else:
                logger.warning("⚠️ OCR attribute not available in this Docling version")

            # Enable table structure if available
            if hasattr(pipeline_options, "do_table_structure"):
                pipeline_options.do_table_structure = True
                logger.info("✅ Table structure detection enabled")

            # Configure GPU acceleration for WSL2 if available
            if hasattr(pipeline_options, "accelerator_device"):
                if self.use_gpu:
                    try:
                        pipeline_options.accelerator_device = "cuda"
                        logger.info("🚀 GPU acceleration enabled (CUDA)")
                    except Exception as e:
                        logger.warning(f"⚠️ GPU acceleration failed, using CPU: {e}")
                        pipeline_options.accelerator_device = "cpu"
                else:
                    pipeline_options.accelerator_device = "cpu"
                    logger.info("🖥️ Using CPU acceleration")
            else:
                logger.info(
                    "⚠️ Accelerator device attribute not available in this Docling version"
                )

            # Create PDF format option with backend
            pdf_format_option = PdfFormatOption(
                pipeline_options=pipeline_options, backend=PyPdfiumDocumentBackend
            )

            # Initialize DocumentConverter
            self.converter = DocumentConverter(
                format_options={InputFormat.PDF: pdf_format_option}
            )

            acceleration_type = "GPU (WSL2)" if self.use_gpu else "CPU"
            logger.info(
                f"✅ Docling initialized successfully with {acceleration_type} acceleration"
            )

        except ImportError as e:
            logger.error(f"❌ Docling not installed: {e}")
            raise RuntimeError(f"Docling not available: {e}") from e
        except Exception as e:
            logger.error(f"❌ Docling initialization failed: {e}")
            raise RuntimeError(f"Docling initialization failed: {e}") from e

    def _configure_easyocr_local_models(self):
        """Configure EasyOCR to use pre-downloaded local models."""
        try:
            import os

            import easyocr

            # Set SSL environment for EasyOCR downloads
            os.environ["CURL_CA_BUNDLE"] = ""
            os.environ["REQUESTS_CA_BUNDLE"] = ""

            # Try to use local models first, fallback to download if needed
            try:
                reader = easyocr.Reader(
                    ["en"],
                    download_enabled=False,
                    model_storage_directory="/root/.EasyOCR/model",
                )
                logger.info("✅ EasyOCR configured for local models")
                return reader
            except Exception:
                # If local models fail, allow download with SSL bypass
                logger.info(
                    "🔄 Local models failed, attempting download with SSL bypass..."
                )
                reader = easyocr.Reader(
                    ["en"],
                    download_enabled=True,
                    model_storage_directory="/root/.EasyOCR/model",
                )
                logger.info("✅ EasyOCR configured with downloaded models")
                return reader
        except Exception as e:
            logger.warning(f"⚠️ EasyOCR configuration failed: {e}")
            return None

    async def process_document(
        self, file_path: str, filename: str | None = None
    ) -> dict[str, Any]:
        """Process document with Docling using pre-downloaded models."""

        if self.converter is None:
            raise RuntimeError("Docling converter not initialized")

        try:
            logger.info(
                f"🔄 Processing {filename} with Docling (using local models)..."
            )

            # Process document with local models
            result = self.converter.convert(file_path)

            # Extract content using version-safe methods
            content = None
            if hasattr(result, "document") and result.document:
                # Try different export methods (version compatibility)
                if hasattr(result.document, "export_to_markdown"):
                    content = result.document.export_to_markdown()
                    logger.info("📄 Used export_to_markdown method")
                elif hasattr(result.document, "to_markdown"):
                    content = result.document.to_markdown()
                    logger.info("📄 Used to_markdown method")
                elif hasattr(result.document, "text"):
                    content = result.document.text
                    logger.info("📄 Used text property")
                elif hasattr(result.document, "__str__"):
                    content = str(result.document)
                    logger.info("📄 Used string conversion")

                if content:
                    logger.info(
                        f"✅ Docling SUCCESS - {filename}: {len(content)} chars (local models)"
                    )

                    return {
                        "content": content,
                        "full_text": content,
                        "service_used": "docling",
                        "status": "success",
                        "processing_notes": "Processed with Docling using pre-downloaded models",
                    }
                else:
                    raise ValueError("No content could be extracted from document")
            else:
                raise ValueError("No document object returned by Docling")

        except Exception as e:
            logger.error(f"❌ Docling processing failed for {filename}: {e}")
            # Log the full error for debugging
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Docling processing failed: {e}") from e

    async def process_large_document_summary(
        self, content: str, llm, document_title: str = "Document"
    ) -> str:
        """
        Process large documents using chunked LLM summarization.

        Args:
            content: The full document content
            llm: The language model to use for summarization
            document_title: Title of the document for context

        Returns:
            Final summary of the document
        """
        # Large document threshold (100K characters ≈ 25K tokens)
        large_document_threshold = 100_000

        if len(content) <= large_document_threshold:
            # For smaller documents, use direct processing
            logger.info(
                f"📄 Document size: {len(content)} chars - using direct processing"
            )
            from app.prompts import SUMMARY_PROMPT_TEMPLATE

            summary_chain = SUMMARY_PROMPT_TEMPLATE | llm
            result = await summary_chain.ainvoke({"document": content})
            return result.content

        logger.info(
            f"📚 Large document detected: {len(content)} chars - using chunked processing"
        )

        # Import chunker from config
        # Create LLM-optimized chunks (8K tokens max for safety)
        from chonkie import OverlapRefinery, RecursiveChunker
        from langchain_core.prompts import PromptTemplate

        llm_chunker = RecursiveChunker(
            chunk_size=8000  # Conservative for most LLMs
        )

        # Apply overlap refinery for context preservation (10% overlap = 800 tokens)
        overlap_refinery = OverlapRefinery(
            context_size=0.1,  # 10% overlap for context preservation
            method="suffix",  # Add next chunk context to current chunk
        )

        # First chunk the content, then apply overlap refinery
        initial_chunks = llm_chunker.chunk(content)
        chunks = overlap_refinery.refine(initial_chunks)
        total_chunks = len(chunks)

        logger.info(f"📄 Split into {total_chunks} chunks for LLM processing")

        # Template for chunk processing
        chunk_template = PromptTemplate(
            input_variables=["chunk", "chunk_number", "total_chunks"],
            template="""<INSTRUCTIONS>
You are summarizing chunk {chunk_number} of {total_chunks} from a large document.

Create a comprehensive summary of this document chunk. Focus on:
- Key concepts, facts, and information
- Important details and context
- Main topics and themes

Provide a clear, structured summary that captures the essential content.

Chunk {chunk_number}/{total_chunks}:
<document_chunk>
{chunk}
</document_chunk>
</INSTRUCTIONS>""",
        )

        # Process each chunk individually
        chunk_summaries = []
        for i, chunk in enumerate(chunks, 1):
            try:
                logger.info(
                    f"🔄 Processing chunk {i}/{total_chunks} ({len(chunk.text)} chars)"
                )

                chunk_chain = chunk_template | llm
                chunk_result = await chunk_chain.ainvoke(
                    {
                        "chunk": chunk.text,
                        "chunk_number": i,
                        "total_chunks": total_chunks,
                    }
                )

                chunk_summary = chunk_result.content
                chunk_summaries.append(f"=== Section {i} ===\n{chunk_summary}")

                logger.info(f"✅ Completed chunk {i}/{total_chunks}")

            except Exception as e:
                logger.error(f"❌ Failed to process chunk {i}/{total_chunks}: {e}")
                chunk_summaries.append(f"=== Section {i} ===\n[Processing failed]")

        # Combine summaries into final document summary
        logger.info(f"🔄 Combining {len(chunk_summaries)} chunk summaries")

        try:
            combine_template = PromptTemplate(
                input_variables=["summaries", "document_title"],
                template="""<INSTRUCTIONS>
You are combining multiple section summaries into a final comprehensive document summary.

Create a unified, coherent summary from the following section summaries of "{document_title}".
Ensure:
- Logical flow and organization
- No redundancy or repetition  
- Comprehensive coverage of all key points
- Professional, objective tone

<section_summaries>
{summaries}
</section_summaries>
</INSTRUCTIONS>""",
            )

            combined_summaries = "\n\n".join(chunk_summaries)
            combine_chain = combine_template | llm

            final_result = await combine_chain.ainvoke(
                {"summaries": combined_summaries, "document_title": document_title}
            )

            final_summary = final_result.content
            logger.info(
                f"✅ Large document processing complete: {len(final_summary)} chars summary"
            )

            return final_summary

        except Exception as e:
            logger.error(f"❌ Failed to combine summaries: {e}")
            # Fallback: return concatenated chunk summaries
            fallback_summary = "\n\n".join(chunk_summaries)
            logger.warning("⚠️ Using fallback combined summary")
            return fallback_summary


def create_docling_service() -> DoclingService:
    """Create a Docling service instance."""
    return DoclingService()
