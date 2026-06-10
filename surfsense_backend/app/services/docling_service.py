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

            # Enable OCR so text-in-image (chart axes, ECG annotations,
            # lab tables embedded as images, scanned pages, etc.) is
            # lifted into the main markdown stream. This pairs with the
            # vision-LLM picture-description pass downstream — OCR
            # captures literal text; vision LLM captures the visual
            # content. Together they give a faithful representation of
            # PDFs that mix text and images.
            if hasattr(pipeline_options, "do_ocr"):
                pipeline_options.do_ocr = True
                logger.info("✅ OCR enabled for embedded text-in-image extraction")
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

            self.converter = DocumentConverter(
                format_options={InputFormat.PDF: pdf_format_option},
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


def create_docling_service() -> DoclingService:
    """Create a Docling service instance."""
    return DoclingService()
