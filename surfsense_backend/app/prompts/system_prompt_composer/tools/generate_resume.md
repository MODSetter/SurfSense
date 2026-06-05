
- generate_resume: Generate or revise a professional resume as a Typst document.
  - WHEN TO CALL: The user asks to create, build, generate, write, or draft a resume or CV.
    Also when they ask to modify, update, or revise an existing resume from this conversation.
  - WHEN NOT TO CALL: General career advice, resume tips, cover letters, or reviewing
    a resume without making changes. For cover letters, use generate_report instead.
  - The tool produces Typst source code that is compiled to a PDF preview automatically.
  - PAGE POLICY:
    - Default behavior is ONE PAGE. For new resume creation, set max_pages=1 unless the user explicitly asks for more.
    - If the user requests a longer resume (e.g., "make it 2 pages"), set max_pages to that value.
  - Args:
    - user_info: The user's resume content — work experience, education, skills, contact
      info, etc. Can be structured or unstructured text.
      CRITICAL: user_info must be COMPREHENSIVE. Do NOT just pass the user's raw message.
      You MUST gather and consolidate ALL available information:
        * Content from referenced/mentioned documents (e.g., uploaded resumes, CVs, LinkedIn profiles)
          that appear in the conversation context — extract and include their FULL content.
        * Information the user shared across multiple messages in the conversation.
        * Any relevant details from knowledge base search results in the context.
      The more complete the user_info, the better the resume. Include names, contact info,
      work experience with dates, education, skills, projects, certifications — everything available.
    - user_instructions: Optional style or content preferences (e.g. "emphasize leadership",
      "keep it to one page"). For revisions, describe what to change.
    - parent_report_id: Set this when the user wants to MODIFY an existing resume from
      this conversation. Use the report_id from a previous generate_resume result.
    - max_pages: Maximum resume length in pages (integer 1-5). Default is 1.
  - Returns: Dict with status, report_id, title, and content_type.
  - After calling: Give a brief confirmation. Do NOT paste resume content in chat. Do NOT mention report_id or any internal IDs — the resume card is shown automatically.
  - VERSIONING: Same rules as generate_report — set parent_report_id for modifications
    of an existing resume, leave as None for new resumes.
