from typing import Literal
from langchain.messages import SystemMessage
from langchain.chat_models import init_chat_model
from langchain_core.messages.base import BaseMessage
from langgraph.types import interrupt
from src.prompts import SUMMARIZATION_PROMPT
import re

model = init_chat_model(
    model= 'gpt-5-nano',
    temperature = 0.8
)


def check_token_usage(individual_turns : list[BaseMessage]) -> Literal['high','low']:
    """ Checks the individual token(words) usage for individual interviews.

      Args:
        individual_turns: List of langchain Messages

      Returns:
        Literal: high or low indicating the token usage
    """
        
    individual_turn_tokens = [len(item.split()) for item in individual_turns]
    total_tokens_used_so_far = 0
    for tokens in individual_turn_tokens:
        total_tokens_used_so_far += int(tokens)

    if total_tokens_used_so_far > 5000:
        # else the input will compund exponentially
        return 'high'
    else: 
        return 'low'

def summarization_middleware(convo_hist: list[BaseMessage]) -> str:
    
    """ Summarizes the conversation history into precise pointers 
         to reduce token context size while keeping most information intact.

      Args:
        convo_hist: List of langchain Messages containing (HumanMessage,AIMessage,SystemMessage) the conversation history of a single ongoing      
        interview

      Returns:
        The summarized pointers in the form of a big string.
    """
    
    response = model.invoke([SystemMessage(content = SUMMARIZATION_PROMPT.format(convo_hist = convo_hist))])
    return response.content

def get_interrupt_response(interrupt_payload: dict) -> [str,str]:
   
    """ Helper function to call interrupt and type check the input and validate actions.
        
        Args: interrupt_payload
        
        Returns: action and feedback (handles empty feedback)"""
        
    response = interrupt(interrupt_payload)
    
    feedback = ""
    action = ""
    
    action = response.get("action", "").strip().lower()
    feedback = response.get("feedback", "").strip()
    
    if not isinstance(response, dict):
        raise ValueError(
            f"Expected interrupt() to return a dict, got {type(response).__name__}"
        )
    
    allowed_actions = interrupt_payload['response_schema']['action']['enum']
    
    if action not in allowed_actions:
        
        raise ValueError(
            f"Invalid action '{action}'. Expected {allowed_actions[0]} or {allowed_actions[1]}."
        )
    
    return [action,feedback] 

def sanitize_latex_code(raw_llm_output: str) -> str:
    """
    Strips out LLM conversational chatter, markdown block quotes, 
    and slices strictly from \\documentclass to \\end{document}.
    #GENERATED USING GPT#
    """
    text = raw_llm_output.strip()

    # 1. Remove markdown code blocks like ```latex ... ``` if present
    code_block_match = re.search(r"```(?:latex)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # 2. Slice strictly from \documentclass to \end{document}
    start_tag = r"\documentclass"
    end_tag = r"\end{document}"

    start_idx = text.find(start_tag)
    end_idx = text.rfind(end_tag)

    if start_idx != -1 and end_idx != -1:
        # Extract purely the LaTeX document scope
        text = text[start_idx : end_idx + len(end_tag)]

    return text.strip()
