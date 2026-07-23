# import required states: 
from src.states import UserSideInput, SingleInterviewState
# general imports: 
from langgraph.graph import StateGraph, START, END

from openai import RateLimitError, APIConnectionError, APITimeoutError
from typing import Callable

# import nodes:
from nodes_and_edges import (input_structuring_node, analyst_creator, HITL, conditional_edge_HITL, generate_and_ask_question, finish_convo, expert_search_query, web_search, answer_question, collect_interviews, content_compiler, latex_compiler,latex_validator, conditional_edge_latex_validation, commit_to_overleaf)

from langgraph.types import RetryPolicy

def LLM_retry_error_filter(error: Exception) -> bool:
    """Only retry network/ratelimit errors"""
    return isinstance(error,(RateLimitError, APIConnectionError, APITimeoutError))

def Tavily_retry_error_filter(error: Exception) -> bool:
    """Only retry network/api errors"""
    return isinstance(error,(ConnectionError, TimeoutError))

LLM_nodes_retry_policy = RetryPolicy(
    initial_interval = 0.5,
    backoff_factor = 2.0,
    max_attempts = 3,
    max_interval = 128,
    jitter = False, # no need to add random variations in retries since no parallel nodes are retrying at same time
    retry_on = LLM_retry_error_filter
)

Tavily_search_node_retry_policy= RetryPolicy(
    initial_interval = 0.5,
    backoff_factor = 2.0,
    max_attempts = 3,
    max_interval = 128,
    jitter = False, 
    retry_on = Tavily_retry_error_filter
)


def add_LLM_node(builder: StateGraph, name_of_node: str, node_funciton: Callable) -> StateGraph:
    """ Returns a node to graph builder with LLM_nodes_retry_policy as retry policy"""
    
    return builder.add_node(name_of_node, node_funciton, retry = LLM_nodes_retry_policy)

def add_Tavily_node(builder: StateGraph, name_of_node: str, node_funciton: Callable) -> StateGraph:
    
    """ Returns a node to graph builder with LLM_nodes_retry_policy as retry policy"""
    
    return builder.add_node(name_of_node, node_funciton, retry = Tavily_search_node_retry_policy)
    

interview_sub_graph = StateGraph(SingleInterviewState)

add_LLM_node(interview_sub_graph, 'analyst' ,generate_and_ask_question)
add_LLM_node(interview_sub_graph,'expert_search', expert_search_query)

add_Tavily_node(interview_sub_graph,'web_search',web_search)

add_LLM_node(interview_sub_graph,'answer_question', answer_question)
add_LLM_node(interview_sub_graph,'collect_interviews',collect_interviews)

interview_sub_graph.add_edge(START, 'analyst')
interview_sub_graph.add_conditional_edges('analyst', finish_convo, ['collect_interviews','expert_search'])
interview_sub_graph.add_edge('expert_search', 'web_search')
interview_sub_graph.add_edge('web_search', 'answer_question')
interview_sub_graph.add_edge('answer_question', 'analyst')
interview_sub_graph.add_edge('collect_interviews',END)


research_graph_builder = StateGraph(UserSideInput)

add_LLM_node(research_graph_builder,'structure_input', input_structuring_node)
add_LLM_node(research_graph_builder,'analyst_creator', analyst_creator)

research_graph_builder.add_node('HITL', HITL) # no llm used here
research_graph_builder.add_node('conduct_interviews', interview_sub_graph.compile())

add_LLM_node(research_graph_builder,'content_compiler',content_compiler)
add_LLM_node(research_graph_builder,'latex_compiler',latex_compiler)
research_graph_builder.add_node('latex_validator', latex_validator)

research_graph_builder.add_node('commit_to_overleaf',commit_to_overleaf) #runs a bash script manually
                        
research_graph_builder.add_edge(START, 'structure_input')
research_graph_builder.add_edge('structure_input', 'analyst_creator')
research_graph_builder.add_edge('analyst_creator', 'HITL')

research_graph_builder.add_conditional_edges('HITL', conditional_edge_HITL, ['analyst_creator', 'conduct_interviews'])
research_graph_builder.add_edge('conduct_interviews','content_compiler')
research_graph_builder.add_edge('content_compiler','latex_compiler')
research_graph_builder.add_edge('latex_compiler', 'latex_validator')
research_graph_builder.add_conditional_edges('latex_validator', conditional_edge_latex_validation, ['latex_compiler','commit_to_overleaf'])
research_graph_builder.add_edge('commit_to_overleaf', END)

research_graph = research_graph_builder.compile()
