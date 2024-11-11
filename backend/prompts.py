# Need to move new prompts to here will move after testing some more

# from langchain_core.prompts.prompt import PromptTemplate
from datetime import datetime, timezone

DATE_TODAY = "Today's date is " + datetime.now(timezone.utc).astimezone().isoformat() + '\n'