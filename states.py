from pydantic import BaseModel, Field
from typing import Optional, Annotated
from langgraph.graph import MessagesState
from operator import add


class Analyst_schema(BaseModel):
    name: Optional[str] = Field(description= 'Name of the analyst', default = None)
    
    pointers_for_interview: list[str] = Field(description = 'Pointers to keep in mind while interviewing an expert.' ,
                                            default = """please respond with 'Thank you for taking time for this interview.' 
                                            Whenever you feel satisfied with the conversation/interview.""") 
    
    skills: list[str] = Field(description = """What are the current skills of the analyst with which we are assuming it to be eligible
    to conduct the interview.""", default_factory = list)
    
    affiliation: str = Field(description = """What is the role with which the analyst is currently associated with 
    like wether it is a department head of it's own company, CEO, Doctor, or a professor,
    or a student or something similar.""", default_factory = str)
    
    experience: str = Field(description = 'Description of the experience of the analyst.', default_factory = str)
    
    responsibility: str = Field(description = """ What are the responsibilities for the analyst for the interview,
    maybe research about more than one topic? """, default_factory = str)


class Analyst_collection(BaseModel): 
    interviewers: list[Analyst_schema] = Field(description = 'List of all the analysts who will be conducting the interview.')


class UserSideInput(MessagesState):
    interviewers: list[Analyst_schema]
    topic: str
    human_feedback: bool = True
    max_analysts: int = 4
    sources : list[str]
    conversation_history_all_agents: Annotated[list,add]  = Field(default_factory=[])
    sources_all_agents: Annotated[list,add] = Field(default_factory=[])
    intro : str = Field(description = 'Intro of the research paper draft by using all the conversation history.')
    body : str 
    final_draft_sources: list[str] = Field(description = """final sources that were used as references to generate the body of the research report""")


class structured_input(BaseModel):
    topic: str
    max_analysts: int



class SingleInterviewState(BaseModel):
    analyst: Analyst_schema
    conversation_history: Annotated[list,add]  = Field(default_factory=[])
    number_of_turns: int = Field(description = """number of times the graph has looped and we reached analysts node""",
                                default = 0)
    # can make this a global variable for user to decide as well?
    web_search_context: Annotated[list,add] = Field(default_factory=[])
    sources: Annotated[list,add] = Field(default_factory=[])
    expert_search_query: str = Field(default_factory='')
    current_question: str = Field(default_factory='')
    current_answer: str = Field(default_factory='')


class Question_Structure(BaseModel):
    question : str = Field(description = 'structure of question to be generated')

class Answer_Structure(BaseModel):
    answer : str = Field(description = 'structure of answer to be generated')

class body_and_sources_struct(BaseModel):
    body : str 
    final_draft_sources: Annotated[list[str],add] = Field(description = """final sources that are used as references to generate the body of       the research report""")
