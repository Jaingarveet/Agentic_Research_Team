from typing import Literal
from langchain.messages import SystemMessage


def check_token_usage(individual_turns : list) -> Literal['high','low']:

    individual_turn_tokens = [len(item.split()) for item in individual_turns]
    total_tokens_used_so_far = 0
    for tokens in individual_turn_tokens:
        total_tokens_used_so_far += int(tokens)

    if total_tokens_used_so_far > 5000:
        # else the input will compund exponentially
        return 'high'
    else: 
        return 'low'

def summarization_middleware(convo_hist: list):
    response = model.invoke([SystemMessage(content = SUMMARIZATION_PROMPT.format(convo_hist = convo_hist))])
    return response.content