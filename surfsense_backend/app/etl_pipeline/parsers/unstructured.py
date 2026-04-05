async def parse_with_unstructured(file_path: str) -> str:
    from langchain_unstructured import UnstructuredLoader

    loader = UnstructuredLoader(
        file_path,
        mode="elements",
        post_processors=[],
        languages=["eng"],
        include_orig_elements=False,
        include_metadata=False,
        strategy="auto",
    )
    docs = await loader.aload()
    return "\n\n".join(doc.page_content for doc in docs if doc.page_content)
