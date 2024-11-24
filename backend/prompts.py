# Need to move new prompts to here will move after testing some more

from langchain_core.prompts.prompt import PromptTemplate
from datetime import datetime, timezone

DATE_TODAY = "Today's date is " + datetime.now(timezone.utc).astimezone().isoformat() + '\n'


report_template = """
You are an eagle-eyed researcher, skilled at summarizing lengthy documents with precision and clarity.
I would like you to assist me in summarizing the following text. Please create a comprehensive summary that captures the main ideas, key details, and essential arguments presented in the text. Your summary should adhere to the following guidelines:

Length and Depth: Provide a detailed summary that is approximately [insert desired word count or length, e.g., 300-500 words]. Ensure that it is thorough enough to convey the core message without losing important nuances.

Structure: Organize the summary logically. Use clear headings and subheadings to delineate different sections or themes within the text. This will help in understanding the flow of ideas.

Key Points: Highlight the main arguments and supporting details. Include any relevant examples or data that reinforce the key points made in the original text.

Clarity and Conciseness: While the summary should be detailed, it should also be clear and concise. Avoid unnecessary jargon or overly complex language to ensure that the summary is accessible to a broad audience.

Objective Tone: Maintain an objective and neutral tone throughout the summary. Avoid personal opinions or interpretations; instead, focus on accurately reflecting the author's intended message.

Conclusion: End the summary with a brief conclusion that encapsulates the overall significance of the text and its implications.

Please summarize the following text:

<text> 
{document}
</text>
"""


report_prompt = PromptTemplate(
    input_variables=["document"],
    template=report_template
)