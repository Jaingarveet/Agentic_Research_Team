import subprocess
import json
from langgraph.types import interrupt
from pydantic import BaseModel
from langgraph.types import Send, Overwrite, Command
from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, AIMessage, HumanMessage
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
     # the last message will be a system message from the input_structuring_node or human_feedback node else a human_feedback
    
    if isinstance(state['messages'][-1], HumanMessage):
        
        final_system_message = [SystemMessage(content = ANALYST_CREATOR_PROMPT.format(max_analysts_number = state['max_analysts'], 
                                                                                      topic = state['topic'])), state['messages'][-1]]

        response  = model.with_structured_output(Analyst_collection).invoke(final_system_message) 
        
        return {'interviewers': response,
                'messages': [AIMessage(content = 'A list of analyst has been generated successfully!')]}
        
    else: 
        
        final_system_message = [SystemMessage(content = ANALYST_CREATOR_PROMPT.format(max_analysts_number = state['max_analysts'], 
                                                                                      topic = state['topic']))]
        
        response  = model.with_structured_output(Analyst_collection).invoke(final_system_message) 
        
        return {'interviewers': response,
                'messages': [AIMessage(content = 'A list of analyst has been generated successfully!')]}

def HITL(state: UserSideInput):
    
    interrupt_payload = {
                "message": "Review analysts",
                "current_analysts": state["interviewers"],
                "response_schema": {
                    "action": {
                        "type": "string",
                        "enum": ["continue", "revise"]
                    },
                    "feedback": {
                        "type": "string"
                    }
                }
            }

    response = interrupt(interrupt_payload)

    feedback = ""
    action = ""

    if not isinstance(response, dict):
        raise ValueError(
            f"Expected interrupt() to return a dict, got {type(response).__name__}"
        )

    action = response.get("action", "").strip().lower()
    feedback = response.get("feedback", "").strip()

    if action not in ["continue", "revise"]:
        raise ValueError(
            f"Invalid action '{action}'. Expected 'continue' or 'revise'."
        )


    # if next_step not in ['continue' ,'revise']:
    #     raise ValueError(f"Invalid input '{next_step}'. Expected 'continue' or 'revise'.")
        
    if action == 'continue':
        return {'messages': [SystemMessage(content = 'User feels satisfied with the list please continue to interview process.')],
               'human_feedback': False}
   
    return {'messages': [HumanMessage(content = feedback) if feedback else SystemMessage(content = 'Revision of analysts is required!.')], 
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
                                          }) for i in range(len(interviewers_list))]


GENERATE_QUESTIONS_PROMPT = """ You are an analyst who is tasked to generate questions to conduct interview with an expert from the 
specified field. Your details are: {analyst_details}. Depending on the conversation time you will also be provided with a conversation history
so far so that you have a historical context to generate more precise questions. 

Try to ask deeper questions on the get go given the fact that you will already have appropriate information about the topic,
Try to keep the conversation as deep as possible in order to extract maximum information with minimal questions.

Generate 1 detailed question at a time!

IMPORTANT NOTE: If you are satisfied with the current conversation and answers please respond back with:
'Thank you for taking time I would like to conclude my interview now!'

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
assistants that has been compiled in one single context and please keep the word length to a maximum of 5000 words. (this is including an introductory paragraph about the body and the actual body, try to use as much detail as possible.)
Please try to go into as detail as possible. 

Introduction: {intro}

Conversation_history: {convo_hist}

Accessed Sources History: {sources_hist}


You are not allowed to return empty handed and also you are not allowed to mention phrases similar to 'User had 4 assistants researching for him/her'.
Just write information regarding the topic by using appropriate info from the conversation history!

All the sources used throughout different conversations will be provided as well and your responsibility is that when you are drafting 
the body of the paper you are also supposed to mention the resource from which that information has been taken from.


NOTE: Please provide sources as a title reference in the places where used throughout the body inside curly brackets. Don't write the sources used in the body as references in the later body part itself rather you are supposed to return them inside the final_draft_sources. Only mention the title of the source in the curly brackets.

NOTE: For final_draft_sources you are supposed to provide the title of the sources used and their actual URLs.
NOTE: You are not supposed to return empty handed in terms of URLs Emphasize on mentioning the source title and it's URL within the final_draft_sources strictly.
"""



def content_compiler(state: UserSideInput):
    
    original_user_requirement = state['topic']
    convo_hist = state['conversation_history_all_agents']
    sources_hist = state['sources_all_agents']
    intro_response = model.invoke(CREATE_INTRO_PROMPT.format(convo_hist = convo_hist, original_user_requirement = original_user_requirement))
    intro = intro_response.content
    body_and_sources_response = model.with_structured_output(body_and_sources_struct).with_config(temperature = 0.8).invoke(CREATE_BODY_AND_SOURCES_PROMPT.format(convo_hist = convo_hist, intro = intro, sources_hist = sources_hist))
    body = body_and_sources_response.body
    sources = body_and_sources_response.final_draft_sources
    
    # We use a model with different temperature to present it more semi-formal writing
    # This might be used as a hyper parameter by user to judge how much formality they want in final report writing.
    return {'intro': intro,
           'body': body,
           'final_draft_sources': sources}
    
CREATE_LATEX_FILE_PROMPT = """ You are given all the contents of a research paper that are to be used and you are tasked with converting that into a LATEX relevant .tex format code. You will be given title, introduction, body, URL sources as content for you to convert it into latex format of .tex. Reminder: You are not allowed to change the internal contents and wordings you will be provided, just try to create the code in executable format that can be directly uploaded to overleaf to compile. 

INTRO: {intro}
BODY: {body}
SOURCES: {sources}
"""

def latex_compiler(state: UserSideInput):

    intro = state['intro']
    body = state['body']
    sources = state['final_draft_sources']
    convo_hist = state['conversation_history_all_agents']
    latex_code_report = model.invoke(CREATE_LATEX_FILE_PROMPT.format(intro = intro, body = body, sources = sources))

    res = subprocess.call(["touch","temp.tex"])
    if res == 0:
        print('Creating a temp.tex file to write the new overleaf code')
        with open('temp.tex','w') as file:
            file.write(latex_code_report.content)
    else:
        print("Not able to create the temp file for storing overleaf code locally.")
    
    return {"messages": []}
    
def commit_to_overleaf(state: UserSideInput):

    # safer to just use a script in background so that no agent is doing non-deterministic control over the commit

    interrupt_payload = {"message": "Please look into introduction, body and the used resources once to approve!",
                "introduction": state['intro'],
                "body": state['body'],
                "sources": state['final_draft_sources'],
                "response_schema": {
                    "action": {
                        "type": "string",
                        "enum": ["continue","end"]
                    }
                }
            }


    response = interrupt(interrupt_payload)
    
    action = ""

    if not isinstance(response, dict):
        raise ValueError(
            f"Expected interrupt() to return a dict, got {type(response).__name__}"
        )

    action = response.get("action", "").strip().lower()

    if action not in ["continue", "end"]:
        raise ValueError(
            f"Invalid action '{action}'. Expected 'continue' or 'revise'."
        )
        
    if action == 'continue':
        
        print('Committing to the repo')
        res = subprocess.call(["bash","script.sh"])
                
        if res == 0:
            print("Successfully committed the report to overleaf")
        else:
            raise (Exception('Difficulty committing to your overleaf repo, check the provided arguments once again please!'))

        return {"messages":[AIMessage(content = "Committed to overleaf project successfully!")]}
   
    return {"messages":[AIMessage(content = "Report generation was successful!")]}
    
# gitignore the bash script? , log files? update the state to remove overleaf_code thing
