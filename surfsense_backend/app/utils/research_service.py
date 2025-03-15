import asyncio
import re
from typing import List, Dict, Any, AsyncGenerator, Callable, Optional
from langchain.schema import Document
from gpt_researcher.agent import GPTResearcher
from gpt_researcher.utils.enum import ReportType, Tone, ReportSource
from dotenv import load_dotenv

load_dotenv()

class ResearchService:
    @staticmethod
    async def create_custom_prompt(user_query: str) -> str:
        citation_prompt = f"""
        You are a research assistant tasked with analyzing documents and providing comprehensive answers with proper citations in IEEE format.

        <instructions>
        1. Carefully analyze all provided documents in the <document> section's.
        2. Extract relevant information that addresses the user's query.
        3. Synthesize a comprehensive, well-structured answer using information from these documents.
        4. For EVERY piece of information you include from the documents, add an IEEE-style citation in square brackets [X] where X is the source_id from the document's metadata.
        5. Make sure ALL factual statements from the documents have proper citations.
        6. If multiple documents support the same point, include all relevant citations [X], [Y].
        7. Present information in a logical, coherent flow.
        8. Use your own words to connect ideas, but cite ALL information from the documents.
        9. If documents contain conflicting information, acknowledge this and present both perspectives with appropriate citations.
        10. Do not make up or include information not found in the provided documents.
        11. CRITICAL: You MUST use the exact source_id value from each document's metadata for citations. Do not create your own citation numbers.
        12. CRITICAL: Every citation MUST be in the IEEE format [X] where X is the exact source_id value.
        13. CRITICAL: Never renumber or reorder citations - always use the original source_id values.
        14. CRITICAL: Do not return citations as clickable links.
        15. CRITICAL: Never format citations as markdown links like "([1](https://example.com))". Always use plain square brackets only.
        16. CRITICAL: Citations must ONLY appear as [X] or [X], [Y], [Z] format - never with parentheses, hyperlinks, or other formatting.
        17. CRITICAL: Never make up citation numbers. Only use source_id values that are explicitly provided in the document metadata.
        18. CRITICAL: If you are unsure about a source_id, do not include a citation rather than guessing or making one up.
        </instructions>

        <format>
        - Write in clear, professional language suitable for academic or technical audiences
        - Organize your response with appropriate paragraphs, headings, and structure
        - Every fact from the documents must have an IEEE-style citation in square brackets [X] where X is the EXACT source_id from the document's metadata
        - Citations should appear at the end of the sentence containing the information they support
        - Multiple citations should be separated by commas: [X], [Y], [Z]
        - No need to return references section. Just citation numbers in answer.
        - NEVER create your own citation numbering system - use the exact source_id values from the documents.
        - NEVER format citations as clickable links or as markdown links like "([1](https://example.com))". Always use plain square brackets only.
        - NEVER make up citation numbers if you are unsure about the source_id. It is better to omit the citation than to guess.
        </format>
        
        <input_example>
            <document>
                <metadata>
                    <source_id>1</source_id>
                </metadata>
                <content>
                    <text>
                        The Great Barrier Reef is the world's largest coral reef system, stretching over 2,300 kilometers along the coast of Queensland, Australia. It comprises over 2,900 individual reefs and 900 islands.
                    </text>
                </content>
            </document>
            
            <document>
                <metadata>
                    <source_id>13</source_id>
                </metadata>
                <content>
                    <text>
                        Climate change poses a significant threat to coral reefs worldwide. Rising ocean temperatures have led to mass coral bleaching events in the Great Barrier Reef in 2016, 2017, and 2020.
                    </text>
                </content>
            </document>
            
            <document>
                <metadata>
                    <source_id>21</source_id>
                </metadata>
                <content>
                    <text>
                        The Great Barrier Reef was designated a UNESCO World Heritage Site in 1981 due to its outstanding universal value and biological diversity. It is home to over 1,500 species of fish and 400 types of coral.
                    </text>
                </content>
            </document>
        </input_example>
        
        <output_example>
            The Great Barrier Reef is the world's largest coral reef system, stretching over 2,300 kilometers along the coast of Queensland, Australia [1]. It was designated a UNESCO World Heritage Site in 1981 due to its outstanding universal value and biological diversity [21]. The reef is home to over 1,500 species of fish and 400 types of coral [21]. Unfortunately, climate change poses a significant threat to coral reefs worldwide, with rising ocean temperatures leading to mass coral bleaching events in the Great Barrier Reef in 2016, 2017, and 2020 [13]. The reef system comprises over 2,900 individual reefs and 900 islands [1], making it an ecological treasure that requires protection from multiple threats [1], [13].
        </output_example>
        
        <incorrect_citation_formats>
        DO NOT use any of these incorrect citation formats:
        - Using parentheses and markdown links: ([1](https://github.com/MODSetter/SurfSense))
        - Using parentheses around brackets: ([1])
        - Using hyperlinked text: [link to source 1](https://example.com)
        - Using footnote style: ... reef system¹
        - Making up citation numbers when source_id is unknown
        
        ONLY use plain square brackets [1] or multiple citations [1], [2], [3]
        </incorrect_citation_formats>
        
        Note that the citation numbers match exactly with the source_id values (1, 13, and 21) and are not renumbered sequentially. Citations follow IEEE style with square brackets and appear at the end of sentences.

        Now, please research the following query:

        <user_query_to_research>
            {user_query}
        </user_query_to_research>
        """
                    
        return citation_prompt
        
        
    @staticmethod
    async def stream_research(
        user_query: str, 
        documents: List[Document] = None,
        on_progress: Optional[Callable] = None,
        research_mode: str = "GENERAL"
    ) -> str:
        """
        Stream the research process using GPTResearcher
        
        Args:
            user_query: The user's query
            documents: List of Document objects to use for research
            on_progress: Optional callback for progress updates
            research_mode: Research mode to use 
            
        Returns:
            str: The final research report
        """
        # Create a custom websocket-like object to capture streaming output
        class StreamingWebsocket:
            async def send_json(self, data):
                if on_progress:
                    try:
                        # Filter out excessive logging of the prompt
                        if data.get("type") == "logs":
                            output = data.get("output", "")
                            # Check if this is a verbose prompt log
                            if "You are a research assistant tasked with analyzing documents" in output and len(output) > 500:
                                # Replace with a shorter message
                                data["output"] = f"Processing research for query: {user_query}"
                        
                        result = await on_progress(data)
                        return result
                    except Exception as e:
                        print(f"Error in on_progress callback: {e}")
                return None
        
        streaming_websocket = StreamingWebsocket()
        
        custom_prompt_for_ieee_citations = await ResearchService.create_custom_prompt(user_query)
        
        if(research_mode == "GENERAL"):
            research_report_type = ReportType.CustomReport.value
        elif(research_mode == "DEEP"):
            research_report_type = ReportType.ResearchReport.value
        elif(research_mode == "DEEPER"):
            research_report_type = ReportType.DetailedReport.value
        # elif(research_mode == "DEEPEST"):
        #     research_report_type = ReportType.DeepResearch.value
        
        # Initialize GPTResearcher with the streaming websocket
        researcher = GPTResearcher(
            query=custom_prompt_for_ieee_citations,
            report_type=research_report_type,
            report_format="IEEE",
            report_source=ReportSource.LangChainDocuments.value,
            tone=Tone.Formal,
            documents=documents,
            verbose=True,
            websocket=streaming_websocket
        )
        
        # Conduct research
        await researcher.conduct_research()
        
        # Generate report with streaming
        report = await researcher.write_report()
        
        # Fix citation format
        report = ResearchService.fix_citation_format(report)
        
        return report 
    
    @staticmethod
    def fix_citation_format(text: str) -> str:
        """
        Fix any incorrectly formatted citations in the text.
        
        Args:
            text: The text to fix
        
        Returns:
            str: The text with fixed citations
        """
        if not text:
            return text
            
        # More specific pattern to match only numeric citations in markdown-style links
        # This matches patterns like ([1](https://github.com/...)) but not general links like ([Click here](https://...))
        pattern = r'\(\[(\d+)\]\((https?://[^\)]+)\)\)'
        
        # Replace with just [X] where X is the number
        text = re.sub(pattern, r'[\1]', text)
        
        # Also match other incorrect formats like ([1]) and convert to [1]
        # Only match if the content inside brackets is a number
        text = re.sub(r'\(\[(\d+)\]\)', r'[\1]', text)
        
        return text