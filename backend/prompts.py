# Need to move new prompts to here will move after testing some more

from langchain_core.prompts.prompt import PromptTemplate
from datetime import datetime, timezone

DATE_TODAY = "Today's date is " + datetime.now(timezone.utc).astimezone().isoformat() + '\n'


report_template = """
You are an eagle-eyed researcher, skilled at summarizing lengthy documents with precision and clarity. Create a comprehensive summary of the provided document, capturing the main ideas, key details, and essential arguments presented.

Length and depth:
- Produce a detailed summary that captures all essential content from the document. Adjust the length as needed to ensure no critical information is omitted.

Structure:
- Organize the summary logically.
- Use clear headings and subheadings for different sections or themes, to help convey the flow of ideas.

Content to Include:
- Highlight the main arguments.
- Identify and include key supporting details.
- Incorporate relevant examples or data that strengthen the key points.

Tone:
- Use an objective, neutral tone, delivering precise and insightful analysis without personal opinions or interpretations.

# Steps

1. **Thoroughly read the entire text** to grasp the author's perspective, main arguments, and overall structure.
2. **Identify key sections or themes** and thematically group the information.
3. **Extract main points** from each section to capture supporting details and relevant examples.
4. **Use headings/subheadings** to provide a clear and logically organized structure.
5. **Write a conclusion** that succinctly encapsulates the overarching message and significance of the text.

# Output Format

- Provide a summary in well-structured paragraphs.
- Clearly delineate different themes or sections with suitable headings or sub-headings.
- Adjust the length of the summary based on the content's complexity and depth.
- Conclusions should be clearly marked.

# Example

**Heading 1: Introduction to Main Theme**  
The document begins by discussing [main idea], outlining [initial point] with supporting data like [example].

**Heading 2: Supporting Arguments**  
The text then presents several supporting arguments, such as [supporting detail]. Notably, [data or statistic] is used to reinforce the main concept.

**Heading 3: Conclusion**  
In summary, [document's conclusion statement], highlighting the broader implications like [significance].

(This is an example format; each section should be expanded comprehensively based on the provided document.) 

# Notes
- Ensure the summary is adequately comprehensive without omitting crucial parts.
- Aim for readability by using formal yet accessible language, maintaining depth without unnecessary complexity.

Now, Please summarize the following document:

<document> 
{document}
</document>
"""


report_prompt = PromptTemplate(
    input_variables=["document"],
    template=report_template
)