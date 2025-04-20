#!/usr/bin/env python3
"""
Test script for the Researcher LangGraph agent.

This script demonstrates how to invoke the researcher agent with a sample query.
Run this script directly from VSCode using the "Run Python File" button or
right-click and select "Run Python File in Terminal".

Before running:
1. Make sure your Python environment has all required dependencies
2. Create a .env file with any required API keys
3. Ensure database connection is properly configured
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path so that 'app' can be found as a module
# Get the absolute path to the surfsense_backend directory which contains the app module
project_root = str(Path(__file__).resolve().parents[3])  # Go up 3 levels from the script: app/agents/researcher -> app/agents -> app -> surfsense_backend
print(f"Adding to Python path: {project_root}")
sys.path.insert(0, project_root)

# Now import the modules after fixing the path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# These imports should now work with the correct path
from app.agents.researcher.graph import graph
from app.agents.researcher.state import State
from app.agents.researcher.nodes import write_answer_outline, process_sections

# Load environment variables
load_dotenv()

# Database connection string - use a test database or mock
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/surfsense"

# Create async engine and session
engine = create_async_engine(DATABASE_URL)
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def run_test():
    """Run a test of the researcher agent."""
    print("Starting researcher agent test...")
    
    # Create a database session
    async with async_session_maker() as db_session:
        # Sample configuration
        config = {
            "configurable": {
                "user_query": "What are the best clash royale decks recommended by Surgical Goblin?",
                "num_sections": 1,
                "connectors_to_search": [
                    "YOUTUBE_VIDEO",
                ],
                "user_id": "d6ac2187-7407-4664-8734-af09926d161e",
                "search_space_id": 2
            }
        }
        
        try:
            # Initialize state with database session and engine
            initial_state = State(db_session=db_session, engine=engine)
            
            # Instead of using the graph directly, let's run the nodes manually
            # to track the state transitions explicitly
            print("\nSTEP 1: Running write_answer_outline node...")
            outline_result = await write_answer_outline(initial_state, config)
            
            # Update the state with the outline
            if "answer_outline" in outline_result:
                initial_state.answer_outline = outline_result["answer_outline"]
                print(f"Generated answer outline with {len(initial_state.answer_outline.answer_outline)} sections")
                
                # Print the outline
                print("\nGenerated Answer Outline:")
                for section in initial_state.answer_outline.answer_outline:
                    print(f"\nSection {section.section_id}: {section.section_title}")
                    print("Research Questions:")
                    for q in section.questions:
                        print(f"  - {q}")
            
            # Run the second node with the updated state
            print("\nSTEP 2: Running process_sections node...")
            sections_result = await process_sections(initial_state, config)
            
            # Check if we got a final report
            if "final_written_report" in sections_result:
                final_report = sections_result["final_written_report"]
                print("\nFinal Research Report generated successfully!")
                print(f"Report length: {len(final_report)} characters")
                
                # Display the final report
                print("\n==== FINAL RESEARCH REPORT ====\n")
                print(final_report)
            else:
                print("\nNo final report was generated.")
                print(f"Result keys: {list(sections_result.keys())}")
            
            return sections_result
            
        except Exception as e:
            print(f"Error running researcher agent: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

async def main():
    """Main entry point for the test script."""
    try:
        result = await run_test()
        print("\nTest completed successfully.")
        return result
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Run the async test
    result = asyncio.run(main())
    
    # Keep terminal open if run directly in VSCode
    if 'VSCODE_PID' in os.environ:
        input("\nPress Enter to close this window...") 