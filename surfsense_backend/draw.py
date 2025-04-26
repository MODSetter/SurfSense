from app.agents.researcher.graph import graph as researcher_graph
from app.agents.researcher.sub_section_writer.graph import graph as sub_section_writer_graph

print(researcher_graph.get_graph().draw_mermaid())
print(sub_section_writer_graph.get_graph().draw_mermaid())