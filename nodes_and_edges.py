from langgraph.types import interrupt
from pydantic import BaseModel
from langgraph.types import Send, Overwrite, Command
from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, AIMessage
from tavily import TavilyClient
from utils import check_token_usage, summarization_middleware
from states import Analyst_schema, Analyst_collection, UserSideInput, structured_input, SingleInterviewState, Question_Structure, Answer_Structure, body_and_sources_struct

model = init_chat_model(
    model= 'gpt-5-nano',
    temperature = 0.5
)


STRUCTURED_INPUT_message = """ Please take the following messages as input and give out a structured output: """

def input_structuring_node(state: UserSideInput):
    messages = state['messages']
    model_invokation_message = [SystemMessage(STRUCTURED_INPUT_message)] + messages
    response = model.with_structured_output(structured_input).invoke(model_invokation_message)
    model_message = [AIMessage(content='Updated the structure of the input for the given messages!')]
    return {'topic': response.topic,
            'max_analysts' : response.max_analysts ,
            'messages': model_message} 

    
ANALYST_CREATOR_PROMPT = """You are tasked to generate a list of deep analysts based on the provided schema, keep in mind that these analysts
will be responsible for conducting interviews with experts in their own sub-domains and you have to make sure that while you are adhering to the 
schema you provide as much details as possible in that. You have to return with atleast 3 analysts which have 80% distinguished sub_domains
and you are not allowed to return empty handed. Appropriate information to be generated has been provided as a structured output to you
and you can also fill in the responsibilities field in the schema with appropriate details along with the pointers.
The maximum_number of analysts you can generate is: {max_analysts_number}
The topic for which you have to create analysts for is {topic}
"""
    
def analyst_creator(state: UserSideInput):
    """ Given a user input schema this function invokes a LLM to generate a list of analyst to conduct specialized interviews"""
     # the last message will be a system message from the input or human_feedback node
    final_system_message = [SystemMessage(content = ANALYST_CREATOR_PROMPT.format(max_analysts_number = state['max_analysts'], 
                                                                                  topic = state['topic']))]
    
    response  = model.with_structured_output(Analyst_collection).invoke(final_system_message) 
    
    return {'interviewers': response,
            'messages': [AIMessage(content = 'A list of analyst has been generated successfully!')]}

def HITL(state: UserSideInput):
    
    interrupt_payload = {
        "message": "Review the generated analysts. Do you want to continue or revise?",
        "topic": state['topic'],
        "current_analysts": state['interviewers'],
        "allowed_responses": ["continue", "revise"]
    }

    user_response = interrupt(interrupt_payload)
    
    if isinstance(user_response, dict):
        next_step = user_response.get('data',"").strip().lower()
    
    else: 
        next_step = str(user_response).strip().lower()

    if next_step not in ['continue' ,'revise']:
        raise ValueError(f"Invalid input '{next_step}'. Expected 'continue' or 'revise'.")
        
    if next_step == 'continue':
        return {'messages': [SystemMessage(content = 'User feels satisfied with the list please continue to interview process.')],
               'human_feedback': False}

    if next_step == 'revise':
        return {'messages': [SystemMessage(content = 'Revision of analysts is required!.')], 
                'human_feedback': True}

def conditional_edge_HITL(state: UserSideInput):
    if state['human_feedback']:
        return 'analyst_creator'
    else:
        print("""<-------Moving onto the interviewing process now!------------->""")

        interviewers_list = state['interviewers'].interviewers
        print('length of interviewers_list: ', len(interviewers_list),
             '\n',
             'number of max analysts: ', state['max_analysts'], 'type', type(state['max_analysts']))
        return [Send('conduct_interviews',{'analyst' : interviewers_list[i],
                                           'conversation_history' : [],
                                            'web_search_context' : [],
                                            'sources' : [],
                                            'expert_search_query' : '',
                                            'current_question' : '',
                                            'current_answer' : '',
                                            'conversation_history_all_agents': [],
                                            'sources_all_agents':[]
                                          }) for i in range(state['max_analysts'])]


GENERATE_QUESTIONS_PROMPT = """ You are an analyst who is tasked to generate questions to conduct interview with an expert from the 
specified field. Your details are: {analyst_details}. Depending on the conversation time you will also be provided with a conversation history
so far so that you have a historical context to generate more precise questions. 

Try to ask deeper questions on the get go given the fact that you will already have appropriate information about the topic,
Try to keep the conversation as deep as possible in order to extract maximum information with minimal questions.

Generate 1 detailed question at a time!

IMPORTANT NOTE: If you are satisfied with the current conversation and answers please respond back with:
'Thank you for taking time I would like to conclude my interview now!'

"""

SUMMARIZATION_PROMPT = """ I would like you to summarize the following conversation in a concise manner without loosing much of the overall context.
You may remove some of the trivial elements from the history but try to keep the most details as intact as possible.

The word limit for summarization should be a maximum of 1000 words. 
Try not to exceed this limit. A little flexibility over this is allowed.

CONVERSATION HISTORY: {convo_hist}
"""


def generate_and_ask_question(state: SingleInterviewState):
# use a summarization function every 20000 tokens 
# can't make this a tool since we need to gaurantee it's run
# create a turn variable in the state as well, >15 means stop convo
    
    conversation_history = state.conversation_history
    num_turns = state.number_of_turns + 1
    
    if check_token_usage(conversation_history) == 'high':
        
        updated_conversation_history = summarization_middleware(conversation_history)

        UPDATED_GENERATE_QUESTIONS_PROMPT = GENERATE_QUESTIONS_PROMPT.format(analyst_details = state.analyst)
        invokation_message = [SystemMessage(content = UPDATED_GENERATE_QUESTIONS_PROMPT)] + [updated_conversation_history]
        
        response = model.with_structured_output(Question_Structure).invoke(invokation_message)
        
        
        return {'current_question': response.question,
               'conversation_history': Overwrite([updated_conversation_history] + [response.question]),
                # Need to overwrite the state if we want to update it with summary and remove previous history
               'number_of_turns': num_turns} 
        
    else: 
            
        UPDATED_GENERATE_QUESTIONS_PROMPT = GENERATE_QUESTIONS_PROMPT.format(analyst_details = state.analyst)
        invokation_message = [SystemMessage(content = UPDATED_GENERATE_QUESTIONS_PROMPT)] + conversation_history
    
        response = model.with_structured_output(Question_Structure).invoke(invokation_message)
        
        return {'current_question': response.question,
               'conversation_history': [response.question],
                # we just add the current conversation question into the history if we don't summarize
                'number_of_turns': num_turns} 

def finish_convo(state: SingleInterviewState):
    
    conversation_history = state.conversation_history
    num_turns = state.number_of_turns
    
    if num_turns > 3:
        return 'collect_interviews'
        
    elif 'Thank you for taking time I would like to conclude my interview now!' in conversation_history[-1]:
        return 'collect_interviews'
    else:
        return 'expert_search'



SEARCH_QUERY_EXPERT_PROMPT = """ You are a domain expert that is tasked with giving answer to heavy questions from a research analyst.
For this purpose you will be provided with the conversation history to phrase the answers in best possible way so that there is minimal
room for counter questioning from the analyst side. 
Now your specific task is to generate a web_search query given this question: {question} 

Please limit the number of words in your search query to a maximum of 30 words!!!

"""

EXPERT_ANSWER_PROMPT = """ You are a domain expert that is tasked with giving answer to heavy questions from a research analyst.
For this purpose you will be provided with the conversation history to phrase the answers in best possible way so that there is minimal
room for counter questioning from the analyst side. 

Now your specific task is to generate a very good answer query given this question: {question} 
Following is a context for you to answer the question: {context}

Try to answer in such a way that might encourage less counter_questioning. 
You are not allowed to return empty handed, you have to return with an answer.!
"""
web_search_client = TavilyClient()

def expert_search_query(state: SingleInterviewState):

    conversation_history = state.conversation_history
    question = conversation_history[-1]
    UPDATED_SEARCH_QUERY_EXPERT_PROMPT = [SystemMessage(content= SEARCH_QUERY_EXPERT_PROMPT.format(question = question))]
    final_invokation_message = UPDATED_SEARCH_QUERY_EXPERT_PROMPT + conversation_history[:-1]
    response = model.invoke(final_invokation_message)
    
    if len(response.content.split()) > 30:
        shorten_query_prompt = 'Pls shorten this query to only 30 words or less: {original_query}'.format(original_query = response.content)
        response = model.invoke(shorten_query_prompt)
        return {"expert_search_query": response.content}
    
    else: 
        return {"expert_search_query": response.content}

def web_search(state: SingleInterviewState):
    
    search_query = state.expert_search_query
    results = web_search_client.search(query = search_query , max_results = 5)
    
    web_search_context = [item['content'] for item in results['results']]
    sources = [item['url'] for item in results['results']]

    return {'web_search_context': web_search_context,
           'sources': sources}

def answer_question(state: SingleInterviewState):

    context = state.web_search_context[-1]
    conversation_history = state.conversation_history
    question = state.current_question
    UPDATED_EXPERT_ANSWER_PROMPT = EXPERT_ANSWER_PROMPT.format(context = context, question = question)
    invokation_prompt = [SystemMessage(content=UPDATED_EXPERT_ANSWER_PROMPT)] + conversation_history

    response = model.with_structured_output(Answer_Structure).invoke(invokation_prompt)

    return {'current_answer': response.answer,
           'conversation_history': [response.answer]}


def collect_interviews(state: SingleInterviewState):
    return Command(update = {'conversation_history_all_agents': state.conversation_history,
                             'sources_all_agents': state.sources},
                              graph = Command.PARENT)


CREATE_INTRO_PROMPT = """ You are tasked to draw out an introductory statement from this topic:{original_user_requirement}.
The overall context is that multiple AI assistants were generated by the user to research for a topic by conversing with domain experts.
Please just draw an introductory statement based on the topic and below mentioned conversation history of individual AI research 
assistants that has been compiled in one single context and please keep the word length to a maximum of 300 words.
Conversation_history: {convo_hist}

You are not allowed to return empty handed and also you are not allowed to mention phrases similar to 'User had 4 assistants researching for him/her'.
Just write information regarding the topic by using appropriate info from the conversation history!
"""


CREATE_BODY_AND_SOURCES_PROMPT = """ You are tasked to draw out a body for a research paper where you will be provided with an appropriate
introduction statement.

The overall context is that multiple AI assistants were generated by the user to research for a topic by conversing with domain experts.
Based on that we have a conversation history between assistants and experts, sources used by the experts to draw out anwers during interviews
and an introductory statement about the whole paper.

Please draw a body for the research paper based on the given context mentioned in this prompt and below mentioned conversation history of individual AI research 
assistants that has been compiled in one single context and please keep the word length to a maximum of 1000 words.

Introduction: {intro}

Conversation_history: {convo_hist}


You are not allowed to return empty handed and also you are not allowed to mention phrases similar to 'User had 4 assistants researching for him/her'.
Just write information regarding the topic by using appropriate info from the conversation history!

All the sources used throughout different conversations will be provided as well and your responsibility is that when you are drafting 
the body of the paper you are also supposed to mention the resource from which that information has been taken from.
One idea you could use to ease your resource compilation is that every conversation history is sequential in some sense so all the sources
are also nested sequentially with respect to nesting of each individual conversation.

NOTE: Please provide sources as a title reference in the places where used throughout the body along with their integer id,
while drawing out the sources section you are supposed to provide a list of sources in which each source will be a list that contains 
a string at the 0 index (containing the source link) and an integer id at the 1 index (containing the id of the source which will also be mapped in the body as well while referencing).
so essentially the overall sources list become a nested list where main_list--(contains)--> individual lists --(contains)--> source, id.
"""



def create_intro(state: UserSideInput):
    
    original_user_requirement = state['topic']
    convo_hist = state['conversation_history_all_agents']
    response = model.invoke(CREATE_INTRO_PROMPT.format(convo_hist = convo_hist, original_user_requirement = original_user_requirement))
    return {'intro': response.content}
    
def create_body_and_sources(state: UserSideInput):

    intro = state['intro']
    convo_hist = state['conversation_history_all_agents']
    response = model.with_structured_output(body_and_sources_struct).with_config(temperature = 0.8).invoke(CREATE_BODY_AND_SOURCES_PROMPT.format(convo_hist = convo_hist, intro = intro))
    
    # We use a model with different temperature to present it more semi-formal writing
    # This might be used as a hyper parameter by user to judge how much formality they want in final report writing.
    return {'body': response.body,
           'final_draft_sources': response.final_draft_sources}
