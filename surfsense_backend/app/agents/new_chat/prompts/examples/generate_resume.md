
- User: "Build me a resume. I'm John Doe, engineer at Acme Corp..."
  - Call: `generate_resume(user_info="John Doe, engineer at Acme Corp...", max_pages=1)`
  - WHY: Has creation verb "build" + resume → call the tool.
- User: "Create my CV with this info: [experience, education, skills]"
  - Call: `generate_resume(user_info="[experience, education, skills]", max_pages=1)`
- User: "Build me a resume" (and there is a resume/CV document in the conversation context)
  - Extract the FULL content from the document in context, then call:
    `generate_resume(user_info="Name: John Doe\nEmail: john@example.com\n\nExperience:\n- Senior Engineer at Acme Corp (2020-2024)\n  Led team of 5...\n\nEducation:\n- BS Computer Science, MIT (2016-2020)\n\nSkills: Python, TypeScript, AWS...", max_pages=1)`
  - WHY: Document content is available in context — extract ALL of it into user_info. Do NOT ignore referenced documents.
- User: (after resume generated) "Change my title to Senior Engineer"
  - Call: `generate_resume(user_info="", user_instructions="Change the job title to Senior Engineer", parent_report_id=<previous_report_id>, max_pages=1)`
  - WHY: Modification verb "change" + refers to existing resume → set parent_report_id.
- User: (after resume generated) "Make this 2 pages and expand projects"
  - Call: `generate_resume(user_info="", user_instructions="Expand projects and keep this to at most 2 pages", parent_report_id=<previous_report_id>, max_pages=2)`
  - WHY: Explicit page increase request → set max_pages to 2.
- User: "How should I structure my resume?"
  - Do NOT call generate_resume. Answer in chat with advice.
  - WHY: No creation/modification verb.
