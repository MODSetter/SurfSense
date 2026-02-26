# SurfSense Test Document

## Overview

This is a **sample markdown document** used for end-to-end testing of the manual
document upload pipeline. It includes various markdown formatting elements.

## Key Features

- Document upload and processing
- Automatic chunking of content
- Embedding generation for semantic search
- Real-time status tracking via ElectricSQL

## Technical Architecture

### Backend Stack

The SurfSense backend is built with:

1. **FastAPI** for the REST API
2. **PostgreSQL** with pgvector for vector storage
3. **Celery** with Redis for background task processing
4. **Docling/Unstructured** for document parsing (ETL)

### Processing Pipeline

Documents go through a multi-stage pipeline:

| Stage | Description |
|-------|-------------|
| Upload | File received via API endpoint |
| Parsing | Content extracted using ETL service |
| Chunking | Text split into semantic chunks |
| Embedding | Vector representations generated |
| Storage | Chunks stored with embeddings in pgvector |

## Code Example

```python
async def process_document(file_path: str) -> Document:
    content = extract_content(file_path)
    chunks = create_chunks(content)
    embeddings = generate_embeddings(chunks)
    return store_document(chunks, embeddings)
```

## Conclusion

This document serves as a test fixture to validate the complete document processing
pipeline from upload through to chunk creation and embedding storage.
