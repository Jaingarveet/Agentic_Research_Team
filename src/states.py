from pydantic import BaseModel, Field
from typing import Optional, Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph import MessagesState
from operator import add


class Audience_Schema(BaseModel): 
    role: Literal["executive", "technical_expert", "academic", "general"] = "general"
    knowledge_level: Literal["high", "medium", "low"] = "medium"
    tone: Literal["formal", "concise", "detailed"] = "formal"
    
class Analyst_schema(BaseModel):
    name: Optional[str] = Field(description= 'Name of the analyst', default = None)
    
    pointers_for_interview: list[str] = Field(description = 'Pointers to keep in mind while interviewing an expert.' ,
                                            default = ["""please respond with 'Thank you for taking time for this interview.' 
                                            Whenever you feel satisfied with the conversation/interview."""]) 
    
    skills: list[str] = Field(description = """What are the current skills of the analyst with which we are assuming it to be eligible
    to conduct the interview.""", default_factory = list)
    
    affiliation: str = Field(description = """What is the role with which the analyst is currently associated with 
    like wether it is a department head of it's own company, CEO, Doctor, or a professor,
    or a student or something similar.""", default_factory = str)
    
    experience: str = Field(description = 'Description of the experience of the analyst.', default_factory = str)
    
    responsibility: str = Field(description = """ What are the responsibilities for the analyst for the interview,
    maybe research about more than one topic? """, default_factory = str)


class Analyst_collection(BaseModel): 
    interviewers: list[Analyst_schema]


class UserSideInput(MessagesState):
    target_audience: Audience_Schema = Field(description = """Description of the target audience for whom the research is being done.""")
    latex_error_attempts: int = Field(default = 0)
    latex_error_logs: Annotated[list,add]
    interviewers: list[Analyst_schema]
    topic: str
    human_feedback: bool = True
    max_analysts: int 
    sources : list[str]
    conversation_history_all_agents: Annotated[list,add]  = Field(default_factory=list)
    sources_all_agents: Annotated[list,add] = Field(default_factory=list)
    intro : str = Field(description = 'Intro of the research paper draft by using all the conversation history.')
    body : str 
    final_draft_sources: list[str] = Field(description = """final sources that were used as references to generate the body of the research report""")
    recursion_num_HITL: int = Field(description =""" number of times user can maximum revise the analysts to avoid infinite loop""", 
                                    default = 0)
    revise_latex: bool = False

class structured_input(BaseModel):
    topic: str
    target_audience: Audience_Schema


class source_item_schema(TypedDict): 
    url: str
    Quality : str | None

class SingleInterviewState(BaseModel):
    analyst: Analyst_schema
    conversation_history: Annotated[list,add]  = Field(default_factory=list)
    number_of_turns: int = Field(description = """number of times the graph has looped and we reached analysts node""",
                                default = 0)
    web_search_context: Annotated[list,add] = Field(default_factory=list)
    sources: Annotated[list,add] = Field(default_factory= list)
    expert_search_query: str = Field(default_factory=str)
    current_question: str = Field(default_factory=str)
    current_answer: str = Field(default_factory=str)
    interviewer_id: int = Field(description = "unique interviewer Id to debug better in traces and graph execution as well")
    ranked_sources: Annotated[list,add] = Field(default_factory= list)


class Question_Structure(BaseModel):
    question : str = Field(description = """ The next question to ask the analyst""")

class Answer_Structure(TypedDict):
    answer : str 
    sources: list[source_item_schema]

class final_draft_source_item_schema(TypedDict):
    title: str
    url: str

# need runtime schema validation for this = BaseModel!
class body_and_sources_struct(BaseModel):
    body : str = Field(description = "body of the draft")
    final_draft_sources: Annotated[list[final_draft_source_item_schema],add] = Field(description = """final sources that are used as references to generate the body of       the research report""")
