from pathlib import Path
import subprocess
from typing import Any, Literal
from pydantic import BaseModel
from langchain_core.messages.base import BaseMessage
from langgraph.types import Send, Overwrite, Command
from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, AIMessage, HumanMessage
from tavily import TavilyClient
from src.utils import check_token_usage, summarization_middleware, get_interrupt_response, sanitize_latex_code
from src.states import Analyst_collection, UserSideInput, structured_input, SingleInterviewState, Question_Structure, Answer_Structure, source_item_schema
from src.prompts import (STRUCTURED_INPUT_message, ANALYST_CREATOR_PROMPT, GENERATE_QUESTIONS_PROMPT, 
           SEARCH_QUERY_EXPERT_PROMPT, EXPERT_ANSWER_PROMPT, EXPERT_RANK_SOURCES_PROMPT, CREATE_INTRO_PROMPT, 
           CREATE_BODY_AND_SOURCES_PROMPT, CREATE_LATEX_FILE_PROMPT, LATEX_REPORT_IMPROVEMENT_PROMPT)

model = init_chat_model(
    model= 'gpt-5-nano',
    temperature = 0.5
)

web_search_client = TavilyClient()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEMP_LATEX_DIR = PROJECT_ROOT / "temp_latex_code"
TEMP_LATEX_VALIDATION_LOG_DIR = PROJECT_ROOT / "temp_latex_code_validation_log"

SCRIPT_LOCATION = PROJECT_ROOT / "scripts" / "script.sh"

TEMP_LATEX_DIR.mkdir(parents=True, exist_ok=True)
TEMP_LATEX_VALIDATION_LOG_DIR.mkdir(parents=True, exist_ok=True)

LATEX_FILE = TEMP_LATEX_DIR / "temp.tex"

def input_structuring_node(state: UserSideInput) -> dict[str,Any]:
    
    """ Structures the user input into usable global state to save token usage on reasoning and ease of access of information

      Args:
        state: Takes the current state as argument

      Returns:
        dictionary object that modifies the current global state of the graph
    """
    
    messages = state['messages']
    model_invokation_message = [SystemMessage(STRUCTURED_INPUT_message)] + messages
    
    response = model.with_structured_output(structured_input, method = 'json_schema', strict = True).invoke(model_invokation_message)
        
    model_message = [AIMessage(content='Updated the structure of the input for the given messages!')]
    
    return {'topic': response.topic,
            'messages': model_message,
           'max_analysts': 4,
           'target_audience': response.target_audience}

    
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

        response  = model.with_structured_output(Analyst_collection, method = 'json_schema', strict = True).invoke(final_system_message) 
        
        return {'interviewers': response.interviewers,
                'messages': [AIMessage(content = 'A list of analyst has been generated successfully!')]}
        
    else: 
        final_system_message = [SystemMessage(content = ANALYST_CREATOR_PROMPT.format(max_analysts_number = state['max_analysts'], 
                                                                                      topic = state['topic']))]
        
        response  = model.with_structured_output(Analyst_collection, method = 'json_schema', strict = True).invoke(final_system_message) 
        
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
    action, feedback = get_interrupt_response(interrupt_payload)
        
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
        
        response = model.with_structured_output(Question_Structure, method = 'json_schema', strict = True).invoke(invokation_message)
        
        return {'current_question': response.question, # to get rid of pydantic serialization issues
               'conversation_history': Overwrite([updated_conversation_history] + [response.question]),
                # Need to overwrite the state if we want to update it with summary and remove previous history
               'number_of_turns': num_turns} 
        
    else: 
        
        UPDATED_GENERATE_QUESTIONS_PROMPT = GENERATE_QUESTIONS_PROMPT.format(analyst_details = state.analyst)
        invokation_message = [SystemMessage(content = UPDATED_GENERATE_QUESTIONS_PROMPT)] + conversation_history
    
        response = model.with_structured_output(Question_Structure, method = 'json_schema', strict = True).invoke(invokation_message)
        
        return {'current_question': response.question,
               'conversation_history': [response.question],
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
    sources = [source_item_schema(url = item['url'], Quality = None) for item in results['results']]

    return {'web_search_context': [web_search_context],
           'sources': [sources]}
    

def answer_question(state: SingleInterviewState) -> dict[str,Any]:
    
    """ Expert Answering node that returns detailed answer based on the web search context and resources obtained using web_search, ranks sources based on their quality of retrieved web-page content
    
      Args:
        state: Takes the local sub-graph state as argument

      Returns:
        dictionary object modifying the local sub-graph state with answer generated by the expert.
    """
    
    context = state.web_search_context[-1]
    conversation_history = state.conversation_history
    # conversation_history is dynamically summarized if high so this is doable input length
    
    question = state.current_question

    latest_sources_url = [item['url'] for item in state.sources[-1]]
    latest_sources_quality = [item['Quality'] for item in state.sources[-1]]
    
    latest_sources_retreived_with_context = [{'url': url,
                                             'quality': quality,
                                             'context': context
                                             } for url,quality,context in zip(latest_sources_url,latest_sources_quality,context)]
    
    UPDATED_EXPERT_RANK_SOURCES_PROMPT = EXPERT_RANK_SOURCES_PROMPT.format(latest_sources_retreived_with_context=  
                                                                           latest_sources_retreived_with_context)
    
    UPDATED_EXPERT_ANSWER_PROMPT = EXPERT_ANSWER_PROMPT.format(context = context, question = question)
    
    invokation_prompt = [SystemMessage(content=UPDATED_EXPERT_ANSWER_PROMPT)] + conversation_history + [SystemMessage(content =
UPDATED_EXPERT_RANK_SOURCES_PROMPT)]

    response = model.with_structured_output(Answer_Structure, method = 'json_schema', strict = True).invoke(invokation_prompt)
        
    # rank sources as well
    return {'current_answer': response['answer'],
           'conversation_history': [response['answer']],
           'ranked_sources': response['sources']}


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
                             'sources_all_agents': state.ranked_sources},
                              graph = Command.PARENT)


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

    Audience_schema = state['target_audience']
    
    intro_response = model.invoke(CREATE_INTRO_PROMPT.format(convo_hist = convo_hist, original_user_requirement = original_user_requirement, Audience_schema = Audience_schema ))
    
    intro = intro_response.content
    
    body_and_sources_response = model.with_config(temperature=0.5).invoke(
        CREATE_BODY_AND_SOURCES_PROMPT.format(
            convo_hist=convo_hist, 
            intro=intro, 
            sources_hist=sources_hist, 
            Audience_schema=Audience_schema
        )
    )
    
    raw_content = body_and_sources_response.content
    
    # Parse the output using the delimiter
    if "===FINAL_SOURCES===" in raw_content:
        body, raw_sources = raw_content.split("===FINAL_SOURCES===")

        body = body.strip()
        
        # Convert the sources text block into an actual Python list
        sources_list = [
            s.strip() for s in raw_sources.strip().split('\n') if s.strip()
        ]
    else:
        # Fallback just in case the LLM forgets the delimiter
        body = raw_content.strip()
        sources_list = []

    return {
        'intro': intro,
        'body': body,
        'final_draft_sources': sources_list
    }

def latex_compiler(state: UserSideInput) -> dict[str,list]:
    
    """ Latex compiling node that compiles the already existing intro,body and sources into a .tex code format to make it runnable on 
        overleaf. 
        
        (For self-healing: it refines the latex code in case there are some compilation error on local level)
        
        PLAUSIBLE FUTURE IMPROVEMENTS: Current strategy uses improvement_prompt containing error logs and the original code but this can be 
        improved using agentic pipeline so that we only modify the core part where the error logs are shown instead of generating full code file 
        again so that it saves token cost in reasoning about full code file and only focus on modifying the particular error logs related content 
        directly. This might be a good idea when our report token and length increases rapidly in production settings.
    
      Args:
        state: Takes the global state as argument

      Returns:
        Dictionary object with empty message since we need to write the given content in a temp file.
    """
    
    latex_error_attempts = state.get('latex_error_attempts',0)
    latex_error_logs = state.get('latex_error_logs',[])

    if 0 < latex_error_attempts <= 5:
        read_file = ""
        with open(LATEX_FILE, 'r') as file:
            read_file = file.read()
        
        formatted_improvement_prompt = LATEX_REPORT_IMPROVEMENT_PROMPT.format(Latest_error = latex_error_logs[-1],
                                                                                 history_of_errors = latex_error_logs,
                                                                                 latex_file_code = str(read_file))
        raw_latex_from_llm = model.invoke(formatted_improvement_prompt)
        clean_latex = sanitize_latex_code(raw_latex_from_llm.content)
        
        with open(LATEX_FILE, 'w') as file:
            read_file = file.write(clean_latex)
        
        return {"messages": []}
    
    intro = state['intro']
    topic = state['topic']
    body = state['body']
    sources = state['final_draft_sources']
    Audience_schema = state['target_audience']
    
    Updated_CREATE_LATEX_FILE_PROMPT = CREATE_LATEX_FILE_PROMPT.format(intro = intro, body = body, sources = sources, 
                                                                       Audience_schema = Audience_schema, topic = topic)
    
    raw_latex_from_llm = model.invoke(Updated_CREATE_LATEX_FILE_PROMPT)
    clean_latex = sanitize_latex_code(raw_latex_from_llm.content)
    
    with open(LATEX_FILE,'w') as file:
        file.write(clean_latex)
    
    return {"messages": []}

def latex_validator(state: UserSideInput) -> dict[str,Any]: 
    
    """ Latex Validator node, this is the core logic of self-healing latex pipeline where we run the latex code locally once,
    and make the error logs only extract useful information about specific lines and relevant positional context.
    
      Args:
        state: Takes the global state as argument

      Returns:
        Dictionary object modifying the global state for error logs, attempt number, boolean of wether revision is required or not
    """
    
    latex_error_attempts = state.get('latex_error_attempts',0)
    
    try:
        res = subprocess.run(["pdflatex", 
                              "-draftmode",
                              "-interaction=nonstopmode",
                              f"-output-directory={TEMP_LATEX_VALIDATION_LOG_DIR}",
                              str(LATEX_FILE)],
            capture_output=True,
            text=True,
            timeout=10)
        # timeout is basically how long to wait for the child process to run and complete else throw TimeoutExpired exception
        
        if res.returncode==0:
            return {'messages': [AIMessage(content = 'Latex code compilation successful!')],
                    'latex_error_logs': [],
                    'revise_latex': False}
        else: 
            full_error_log = res.stdout.split('\n')
            relevant_error_log = []

            if 'Unknown compilation error.' in full_error_log[-1]:
                raise Exception("Unkown Compilation error")
            
            for i, line in enumerate(full_error_log):
                if line.startswith('!'):
                    relevant_error_log.append(line)
                    for j in range(1,4):
                        if i + j < len(full_error_log) and not full_error_log[i + j].startswith('!'):
                            relevant_error_log.append(full_error_log[i + j])
                    relevant_error_log.append('********' * 5)

            if not relevant_error_log:
                fallback_log = "\n".join(full_error_log[-15:])
                formatted_error = f"Unparsed error. Raw tail log:\n{fallback_log}"

            else:
                formatted_error = "\n".join(relevant_error_log)

            return {'latex_error_logs': [formatted_error],
                    'latex_error_attempts': latex_error_attempts + 1,
                    'revise_latex': True}

    except subprocess.TimeoutExpired as e: 
         raise Exception(f""" Compilation Timeout occurred while trying to run the latex file locally, Error: {str(e)}""")

    
    except Exception as e:
        raise Exception(f"Critical error in latex code validation compilation run: {str(e)}")

def conditional_edge_latex_validation(state: UserSideInput) -> Literal['latex_compiler','commit_to_overleaf']: 
    """ Conditional edge to re-route in case the latex validation is required or not, also checks on wether the attempts to revise has been 
    exhausted or not.
    
      Args:
        state: Takes the global state as argument

      Returns:
        Literal: node names based on relevant conditions: latex_compiler or commit_to_overleaf
    """
    
    if state['revise_latex'] and (state['latex_error_attempts']<=5):
        return 'latex_compiler'
    else : 
        return 'commit_to_overleaf'


def commit_to_overleaf(state: UserSideInput) -> dict[str,list[BaseMessage]]:
    
    """ This node is used to commit the temp.tex file created in previous node to overleaf using bash script.
        The bash script runs a git version control over the overleaf project and commits the new report to that.
        Bash script exits with a status code of 0 if commit was success else we directly raise error so that we don't 
        have any risky code getting access to the overleaf file.
        
      Args:
        Only need the global state to access information to create interrupt payload

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
    
    action, _ = get_interrupt_response(interrupt_payload)
        
    if action == 'continue':
        
        result = subprocess.run(
            ["bash", str(SCRIPT_LOCATION)],
            capture_output=True,
            text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Commit failed.\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
        
        return {"messages": [AIMessage(content="Committed to Overleaf project successfully!")]}
   
    return {"messages":[AIMessage(content = """ Report generation was successful!, checkout the contens in temp.tex file, haven't committed to overleaf yet. """)]}
