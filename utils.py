from typing import Literal
from langchain.messages import SystemMessage
from langchain.chat_models import init_chat_model

SUMMARIZATION_PROMPT = """ I would like you to summarize the following conversation in a concise manner without loosing much of the overall context.
You may remove some of the trivial elements from the history but try to keep the most details as intact as possible.

The word limit for summarization should be a maximum of 1000 words. 
Try not to exceed this limit. A little flexibility over this is allowed.

CONVERSATION HISTORY: {convo_hist}
"""


model = init_chat_model(
    model= 'gpt-5-nano',
    temperature = 0.8
)


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

def summarization_middleware(convo_hist: list ):
    response = model.invoke([SystemMessage(content = SUMMARIZATION_PROMPT.format(convo_hist = convo_hist))])
    return response.content
