# import nodes:
from nodes_and_edges import input_structuring_node, analyst_creator, HITL, conditional_edge_HITL, generate_and_ask_question, finish_convo, expert_search_query, web_search, answer_question, collect_interviews, create_intro, create_body_and_sources

# general imports: 
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver


interview_sub_graph = StateGraph(SingleInterviewState)
interview_sub_graph.add_node('analyst',generate_and_ask_question)
interview_sub_graph.add_node('expert_search', expert_search_query)
interview_sub_graph.add_node('web_search',web_search)
interview_sub_graph.add_node('answer_question', answer_question)
interview_sub_graph.add_node('collect_interviews',collect_interviews)

interview_sub_graph.add_edge(START, 'analyst')
interview_sub_graph.add_conditional_edges('analyst', finish_convo, ['collect_interviews','expert_search'])
interview_sub_graph.add_edge('expert_search', 'web_search')
interview_sub_graph.add_edge('web_search', 'answer_question')
interview_sub_graph.add_edge('answer_question', 'analyst')
interview_sub_graph.add_edge('collect_interviews',END)


research_graph_builder = StateGraph(UserSideInput)
research_graph_builder.add_node('structure_input', input_structuring_node)
research_graph_builder.add_node('analyst_creator', analyst_creator)
research_graph_builder.add_node('HITL', HITL)
research_graph_builder.add_node('conduct_interviews', interview_sub_graph.compile())
research_graph_builder.add_node('create_intro',create_intro)
research_graph_builder.add_node('create_body_and_sources',create_body_and_sources)
                        
research_graph_builder.add_edge(START, 'structure_input')
research_graph_builder.add_edge('structure_input', 'analyst_creator')
research_graph_builder.add_edge('analyst_creator', 'HITL')

research_graph_builder.add_conditional_edges('HITL', conditional_edge_HITL, ['analyst_creator', 'conduct_interviews'])
research_graph_builder.add_edge('conduct_interviews','create_intro')
research_graph_builder.add_edge('create_intro','create_body_and_sources')
research_graph_builder.add_edge('create_body_and_sources', END)


research_graph = research_graph_builder.compile()