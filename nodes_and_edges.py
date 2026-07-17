import subprocess
from langgraph.types import interrupt
from typing import Any, Literal
from pydantic import BaseModel
from langchain_core.messages.base import BaseMessage
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

def input_structuring_node(state: UserSideInput) -> dict[str,Any]:
    
    """ Structures the user input into usable global state to save token usage on reasoning and ease of access of information

      Args:
        state: Takes the current state as argument

      Returns:
        dictionary object that modifies the current global state of the graph
    """
    
    messages = state['messages']
    model_invokation_message = [SystemMessage(STRUCTURED_INPUT_message)] + messages
    
    response = model.with_structured_output(structured_input).invoke(model_invokation_message)
        
    model_message = [AIMessage(content='Updated the structure of the input for the given messages!')]
    
    return {'topic': response['topic'],
            'messages': model_message,
           'max_analysts': 4}

    
ANALYST_CREATOR_PROMPT = """You are tasked to generate a list of deep analysts based on the provided schema, keep in mind that these analysts
will be responsible for conducting interviews with experts in their own sub-domains and you have to make sure that while you are adhering to the 
schema you provide as much details as possible in that. You have to return with analysts which have 80% distinguished sub_domains
and you are not allowed to return empty handed. Appropriate information to be generated has been provided as a structured output to you
and you can also fill in the responsibilities field in the schema with appropriate details along with the pointers.
The maximum_number of analysts you can generate is: {max_analysts_number}
The topic for which you have to create analysts for is {topic}
"""
    
def analyst_creator(state: UserSideInput) -> dict[str,Any]:
    
    """ Used to create analysts given the user requirement obtained from global state.
        Note: it also conducts a check on messages to see if there was any feedback obtained from user after HITL as the last message in the state
        based on that it updates the invokation prompt to create analysts

      Args:
        state: Takes the current state as argument

      Returns:
        dictionary object that modifies the current global state of the graph with new analysts/interviewrs created
    """


    if isinstance(state['messages'][-1], HumanMessage):
                
        final_system_message = [SystemMessage(content = ANALYST_CREATOR_PROMPT.format(max_analysts_number = state['max_analysts'], 
                                                                                      topic = state['topic'])), state['messages'][-1]]

        response  = model.with_structured_output(Analyst_collection).invoke(final_system_message) 
                
        return {'interviewers': response.interviewers,
                'messages': [AIMessage(content = 'A list of analyst has been generated successfully!')]}
        
    else: 
        final_system_message = [SystemMessage(content = ANALYST_CREATOR_PROMPT.format(max_analysts_number = state['max_analysts'], 
                                                                                      topic = state['topic']))]
        
        response  = model.with_structured_output(Analyst_collection).invoke(final_system_message) 
                
        return {'interviewers': response.interviewers,
                'messages': [AIMessage(content = 'A list of analyst has been generated successfully!')]}

def HITL(state: UserSideInput) -> dict[str,Any]:
    
    """ HumanInTheLoop middleware that interrupts the run and asks user wether to continue or with the run or revise the analysts created.
        provides option to give feedback on analysts created and does type checks on the input.

      Args:
        state: Takes the current state as argument

      Returns:
        dictionary object modifying the global state with the HITL feedback info
    """

    # add a recursion limit variable inside this -> prevents infinite loop else might have needed a fallback strategy 
    recursion_num_HITL = state.get('recursion_num_HITL',0) + 1

    if recursion_num_HITL > 5:
        return {'messages': [SystemMessage(content = 'User feels satisfied with the list please continue to interview process.')],
               'human_feedback': False,
               "recursion_num_HITL": recursion_num_HITL}
    
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
    # I wanted to raise errors to get rid of the union return type check when returning erros, this might change in production obviously
    
    action = response.get("action", "").strip().lower()
    feedback = response.get("feedback", "").strip()

    if action not in ["continue", "revise"]:
        raise ValueError(
            f"Invalid action '{action}'. Expected 'continue' or 'revise'."
        )
        
    if action == 'continue':
                
        return {'messages': [SystemMessage(content = 'User feels satisfied with the list please continue to interview process.')],
               'human_feedback': False,
               "recursion_num_HITL": recursion_num_HITL}
        
    return {'messages': [HumanMessage(content = feedback) if feedback else SystemMessage(content = 'Revision of analysts is required!.')], 
            'human_feedback': True,
           'recursion_num_HITL': recursion_num_HITL}
   

def conditional_edge_HITL(state: UserSideInput) -> str | list[Send]:
        
    """ Conditional edge that checks if the human_feedback is true or not and routes the current run accordingly.

      Args:
        state: Takes the current state as argument

      Returns:
        routes to the next node in graph based on the feedback condition, node can either be the analyst_creator or a sub-graph that 
        conducts parallel interviews using Send api of langgraph
    """

    if state['human_feedback']:
        return 'analyst_creator'
    else:
        
        interviewers_list = state['interviewers']
                
        return [Send('conduct_interviews',{'analyst' : interviewers_list[i],
                                           'conversation_history' : [],
                                            'web_search_context' : [],
                                            'sources' : [],
                                            'expert_search_query' : '',
                                            'current_question' : '',
                                            'current_answer' : '',
                                            'conversation_history_all_agents': [],
                                            'sources_all_agents':[],
                                            'interviewer_id': int(i+1)}) 
                                            for i in range(len(interviewers_list))]
        
        # no need to validate data since we send it manually and create on our side


GENERATE_QUESTIONS_PROMPT = """ You are an analyst who is tasked to generate questions to conduct interview with an expert from the 
specified field. Your details are: {analyst_details}. Depending on the conversation time you will also be provided with a conversation history
so far so that you have a historical context to generate more precise questions. 

Try to ask deeper questions on the get go given the fact that you will already have appropriate information about the topic,
Try to keep the conversation as deep as possible in order to extract maximum information with minimal questions.

Generate 1 detailed question at a time!

IMPORTANT NOTE: If you are satisfied with the current conversation and answers please respond back with:
'Thank you for taking time I would like to conclude my interview now!'

"""


def generate_and_ask_question(state: SingleInterviewState) -> dict[str,Any]:
        
    """ Technically this can be interpreted as the analyst node in interview sub-graph,
        main use case of this node is: 
        - use a summarization middleware every 5000 tokens
        - generates detailed questions to ask a domain expert
        
      Args:
        state: Takes the local sub-graph state as argument

      Returns:
        dictionary object modifying the local state of the interview sub-graph with conversation_history, number of turns(increment)
        ,current_question    
    """
        
    conversation_history = state.conversation_history
    num_turns = state.number_of_turns + 1
    
    if check_token_usage(conversation_history) == 'high':
        
        updated_conversation_history = summarization_middleware(conversation_history)

        UPDATED_GENERATE_QUESTIONS_PROMPT = GENERATE_QUESTIONS_PROMPT.format(analyst_details = state.analyst)
        invokation_message = [SystemMessage(content = UPDATED_GENERATE_QUESTIONS_PROMPT)] + [updated_conversation_history]
        
        response = model.with_structured_output(Question_Structure).invoke(invokation_message)
                
        return {'current_question': response['question'], # to get rid of pydantic serialization issues
               'conversation_history': Overwrite([updated_conversation_history] + [response['question']]),
                # Need to overwrite the state if we want to update it with summary and remove previous history
               'number_of_turns': num_turns} 
        
    else: 
        
        UPDATED_GENERATE_QUESTIONS_PROMPT = GENERATE_QUESTIONS_PROMPT.format(analyst_details = state.analyst)
        invokation_message = [SystemMessage(content = UPDATED_GENERATE_QUESTIONS_PROMPT)] + conversation_history
    
        response = model.with_structured_output(Question_Structure).invoke(invokation_message)
    
        return {'current_question': response['question'],
               'conversation_history': [response['question']],
                # we just add the current conversation question into the history if we don't summarize
                'number_of_turns': num_turns} 

def finish_convo(state: SingleInterviewState) -> Literal['collect_interviews', 'expert_search']:
            
    """ Conditional edge that checks if conversation is concluded based on number of turns or analyst's concluding 
        statement.
        
      Args:
        state: Takes the local sub-graph state as argument

      Returns:
        Literal of collect_interview or expert_search to route the graph accordingly
    """
    
    conversation_history = state.conversation_history
    num_turns = state.number_of_turns
    
    if num_turns > 5:
                
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

def expert_search_query(state: SingleInterviewState) -> dict[str,Any]:
            
    """ Expert node in the local-graph that is forced to generate a web-search query in order to maximize legitimate information without 
        assumption of LLMs. 
        Note: it also forces the model to shorten query length since TavilyAPI only works under 400 character limit of 
        the search query. 
        
      Args:
        state: Takes the local sub-graph state as argument

      Returns:
        dictionary object modifying the local sub-graph state with the search query generated by the expert.
    
    Note: Since LLMs are very adaptive the domain things is working in the sense that expert node will automatically start adapting to 
    questions and history making it domain specific which is extended using personalities.
    """
    
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

def web_search(state: SingleInterviewState) -> dict[str,Any]:
            
    """ Web_search node that returns URLs to be used as sources and their content to be used as context
        Note: Tavily Api is used here for easier search but can be replaced and extended with Wikipedia and ArXiv api as well.
        
      Args:
        state: Takes the local sub-graph state as argument

      Returns:
        dictionary object modifying the local sub-graph state with search context and sources.
    """
    
    search_query = state.expert_search_query
    results = web_search_client.search(query = search_query , max_results = 5)
        
    web_search_context = [item['content'] for item in results['results']]
    sources = [item['url'] for item in results['results']]

    return {'web_search_context': web_search_context,
           'sources': sources}

def answer_question(state: SingleInterviewState) -> dict[str,Any]:
    
    """ Expert Answering node that returns detailed answer based on the web search context and resources obtained using web_search
    
      Args:
        state: Takes the local sub-graph state as argument

      Returns:
        dictionary object modifying the local sub-graph state with answer generated by the expert.
    """
    
    context = state.web_search_context[-1]
    conversation_history = state.conversation_history
    question = state.current_question
    UPDATED_EXPERT_ANSWER_PROMPT = EXPERT_ANSWER_PROMPT.format(context = context, question = question)
    invokation_prompt = [SystemMessage(content=UPDATED_EXPERT_ANSWER_PROMPT)] + conversation_history

    response = model.with_structured_output(Answer_Structure).invoke(invokation_prompt)

    return {'current_answer': response['answer'],
           'conversation_history': [response['answer']]}


def collect_interviews(state: SingleInterviewState) -> Command:
    
    """ Node to collect interview and update the global state using appropriate reducers (Annotated[str,add]) and Command api for the 
        conversation history and sources used in the single interview.
    
      Args:
        state: Takes the local sub-graph state as argument

      Returns:
        Command API object to update the parent graph by adding the current history and sources of the interview to the collection in 
        global state. 
        
        NOTE: Global state keys contain Annotated add operator to acts as reducer so that our sub-graph node doesn't 
        overwrite and only appends the conversation history and sources.
    """
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
the body of the paper you are also supposed to mention the resource from which that information has been taken from. Sources are supposed to be returned in format of title 

NOTE: Please provide sources as a title reference in the places where used throughout the body inside curly brackets. Don't write the sources used in the body as references in the later body part itself rather you are supposed to return them inside the final_draft_sources. Only mention the title of the source in the curly brackets.

NOTE: For final_draft_sources you are supposed to provide the title of the sources used and their actual URLs. You are not supposed to return empty handed in terms of URLs Emphasize on mentioning the source title and it's URL within the final_draft_sources strictly.
"""



def content_compiler(state: UserSideInput) -> dict[str,Any]:
    
    """ Content compiling node that compiles the conversation history and sources across all interviews in a report format in order to 
        obtain a detailed technical research paper consisting of intro, body, sources.
    
      Args:
        state: Takes the global state as argument

      Returns:
       Dictionary object updating the global state with body,sources and introduction of the final report
       
       NOTE: The body mentions the title of the sources used inside curly brackets and the sources/final_draf_sources key is what actually 
       stores the title of sources along with URLs. Also the compiling prompt has been set in a way that allows the model to understand 
       what resources to refer at which point of writing the body.
    """
    
    original_user_requirement = state['topic']
    convo_hist = state['conversation_history_all_agents']
    sources_hist = state['sources_all_agents']
    
    intro_response = model.invoke(CREATE_INTRO_PROMPT.format(convo_hist = convo_hist, original_user_requirement = original_user_requirement))
    intro = intro_response.content
    body_and_sources_response = model.with_structured_output(body_and_sources_struct).with_config(temperature = 0.8).invoke(CREATE_BODY_AND_SOURCES_PROMPT.format(convo_hist = convo_hist, intro = intro, sources_hist = sources_hist))
    
    body = body_and_sources_response.body
    sources = body_and_sources_response.final_draft_sources
         
    return {'intro': intro,
           'body': body,
           'final_draft_sources': sources}

CREATE_LATEX_FILE_PROMPT = """ You are given all the contents of a research paper that are to be used and you are tasked with converting that into a LATEX relevant .tex format code. You will be given title, introduction, body, URL sources as content for you to convert it into latex format of .tex. Reminder: You are not allowed to change the internal contents and wordings you will be provided, just try to create the code in executable format that can be directly uploaded to overleaf to compile. 

INTRO: {intro}
BODY: {body}
SOURCES: {sources}

Additional LaTeX Best Practices:

1. **Indentation and Spacing:**
   - Use consistent indentation, preferably three spaces, to enhance readability.
   - Add blank lines between packages and definitions to keep the code organized.

2. **Preamble:**
   - Place one class option per line.
   - Group related settings and use comments to explain sections.

3. **Document Body:**
   - Use the `align` environment for multi-line equations instead of `eqnarray`, which is deprecated.
   - Define custom commands for frequently used symbols or terms to maintain consistency and readability.
   - Avoid hardcoding formatting commands like `\vspace` or `\hspace`; rely on LaTeX's default spacing unless absolutely necessary.

4. **Math Typesetting:**
   - Use `\prescript` for complex superscript and subscript arrangements.
   - Prefer `$begin:math:text$ ... $end:math:text$` for inline math and `$begin:math:display$ ... $end:math:display$` for display math instead of the dollar sign notation.
   - Utilize the `physics` package for common physics notation and the `siunitx` package for consistent unit formatting.

5. **Referencing:**
   - Use `\eqref` for equations to ensure correct formatting with parentheses.
   - Prefix labels with `eq:`, `fig:`, `tab:`, or `sec:` to indicate the type of reference.

6. **Figures and Tables:**
   - Place figures in the `figure` environment and tables in the `table` environment to let LaTeX handle their placement.
   - Use the `booktabs` package for well-formatted tables.

7. **Text Formatting:**
   - Place a non-breaking space (`~`) between a citation and the preceding word to avoid awkward line breaks.
   - Use `microtype` for enhanced text justification and character protrusion.

"""

def latex_compiler(state: UserSideInput) -> dict[str,[]]:
    
    """ Latex compiling node that compiles the already existing intro,body and sources into a .tex code format to make it runnable on 
        overleaf.
    
      Args:
        state: Takes the global state as argument

      Returns:
        Dictionary object with empty message since we need to write the given content in a temp file.
    """
    
    intro = state['intro']
    body = state['body']
    sources = state['final_draft_sources']
    convo_hist = state['conversation_history_all_agents']
    
    latex_code_report = model.invoke(CREATE_LATEX_FILE_PROMPT.format(intro = intro, body = body, sources = sources))
        
    with open('temp.tex','w') as file:
        file.write(latex_code_report.content)
    
    return {"messages": []}
    
def commit_to_overleaf(state: UserSideInput) -> dict[str,list[BaseMessage]]:
    
    """ This node is used to commit the temp.tex file created in previous node to overleaf using bash script.
        The bash script runs a git version control over the overleaf project and commits the new report to that.
        
      Args:
        No argument needed since we don't retrieve any information from the state even though langgraph still passes the global 
        state to every node at it's level.

      Returns:
        Dictionary object with message from AI that report generation was successful.

        NOTE: Safer to just use a script in background so that no agent is doing non-deterministic control over the commit,
              Providing commit functionality as a tool to agent introduces non-determinism!.
    """

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
        
        result = subprocess.run(
            ["bash", "script.sh"],
            capture_output=True,
            text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Commit failed.\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
        
        return {"messages": [AIMessage(content="Committed to Overleaf project successfully!")]}
   
    return {"messages":[AIMessage(content = "Report generation was successful!")]}
