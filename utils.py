from typing import Literal
from langchain.messages import SystemMessage
from langchain.chat_models import init_chat_model
from langchain_core.messages.base import BaseMessage
from langgraph.types import interrupt


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

def get_prompts():
    
    STRUCTURED_INPUT_message = """ Please take the following messages as input and give out a structured output as if this was a title of a professional research paper. The title should be precise regardless of user's input. Also please generate an Audience profile given user's input or not. 

CRITICAL (EXPLICIT_INSTRUCTIONS): ** In case there is some details about the target audience not given by the user please stick to these values:
    role: "general"
    knowledge_level: "medium"
    tone: "formal"

- User's input: """

     
    ANALYST_CREATOR_PROMPT = """ Your TASK: 
- You are tasked to generate a list of deep analysts based on the provided schema, keep in mind that these analysts will be responsible for conducting interviews with experts in their own sub-domains and you have to make sure that while you are adhering to the 
schema you provide as much details as possible in that. 
- You have to return with analysts which have 80% distinguished sub_domains.
- Appropriate information to be generated has been provided as a structured output to you
and you can also fill in the responsibilities field in the schema with appropriate details along with the pointers.

- The maximum_number of analysts you can generate is: {max_analysts_number}
- The topic for which you have to create analysts for is {topic}

NOTE: 
** You are not allowed to return empty handed. 
"""
    
    GENERATE_QUESTIONS_PROMPT = """ Your task: 
- You are an analyst who is tasked to generate questions to conduct interview with an expert from the 
specified field. 
- Your details are: {analyst_details}. 
- Depending on the conversation time you will also be provided with a conversation history
so far so that you have a historical context to generate more precise questions. 

NOTE: 
** Try to ask deeper questions on the get go given the fact that you will already have appropriate information about the topic,
** Try to keep the conversation as deep as possible in order to extract maximum information with minimal questions.

** Generate 1 detailed question at a time!

IMPORTANT NOTE (EXPLICIT_INSTRUCTIONS): 
** If you are satisfied with the current conversation and answers please respond back with: 'Thank you for taking time I would like to conclude my interview now!'

"""
    
    SEARCH_QUERY_EXPERT_PROMPT = """ Your TASK: 
- You are a domain expert that is tasked with giving answer to heavy questions from a research analyst.
- For this purpose you will be provided with the conversation history to phrase the answers in best possible way so that there is minimal
room for counter questioning from the analyst side. 
- Now your specific task is to generate a web_search query given this question: {question} 

NOTE (EXPLICIT_INSTRUCTIONS): 
** Please limit the number of words in your search query to a maximum of 30 words!!!

"""

    EXPERT_ANSWER_PROMPT = """ Your TASK: 
- You are a domain expert that is tasked with giving answer to heavy questions from a research analyst.
- For this purpose you will be provided with the conversation history to phrase the answers in best possible way so that there is minimal
room for counter questioning from the analyst side. 

- Now your specific task is to generate a very good answer query given this question: 

<QUESTION>
{question}
</QUESTION>

- Following is a context for you to answer the question: 

<CONTEXT>
{context}
</CONTEXT>

NOTE (EXPLICIT_INSTRUCTIONS): 
** Try to answer in such a way that might encourage less counter_questioning. 
** You are not allowed to return empty handed, you have to return with an answer.!
"""


    EXPERT_RANK_SOURCES_PROMPT = """ We have these latest sources: 
    <LATEST SOURCES WITH CONTEXT>
    {latest_sources_retreived_with_context}
    </LATEST SOURCES WITH CONTEXT>
    
This is a list of tuples which contains the source URL, quality(set to default none before prompting you), the context retrieved from that URL.

Your Task: 
- Your task as an expert is to rank these sources in terms of the quality of retrieved context. 
- You can choose [Good, Moderate, Unfavourable] as options to rank the source quality.

NOTE (EXPLICIT_INSTRUCTIONS): 
** Please strictly follow these ranking options, not allowed to return empty handed."""

 
    CREATE_INTRO_PROMPT = """  Your instructions are as follows: 
- You are an expert report compiler translating research summaries into flawless introduction to be used in a report.

- Draw out an introductory statement from this topic which is an original user requirement:{original_user_requirement}.

- The overall context is that multiple AI assistants were generated by the user to research for a topic by conversing with domain experts and then compile it into one report as an analyst report. The current task is to generate the introduction for that report.

-Draw an introductory statement based on the topic and below mentioned conversation history of individual AI research 
assistants that has been compiled in one single context and please keep the word length to a maximum of 300 words.

<CONVERSATION HISTORY> 
{convo_hist}
</CONVERSATION HISTORY>


EXPLICIT_INSTRUCTIONS:
    NOTE: 
    ** You are not allowed to return empty handed and also you are not allowed to mention phrases similar to 'User had 4 assistants researching for him/her'.
    ** Just write information regarding the topic by using appropriate info from the conversation history!
    
    CRITICAL** Following is the information for the targeted audience of this report, please try to use this information strictly to refine your output: {Audience_schema}
"""

# add audience profile in this
    CREATE_BODY_AND_SOURCES_PROMPT = """  
You are an expert, authoritative industry analyst drafting the main body of a comprehensive research report. 

<INTRODUCTION_PROVIDED>
{intro}
</INTRODUCTION_PROVIDED>

<CONVERSATION_HISTORY>
{convo_hist}
</CONVERSATION_HISTORY>

<ACCESSED_SOURCE_HISTORY>
{sources_hist}
</ACCESSED_SOURCE_HISTORY>

Your exact instructions for generating the report body:

1. SEAMLESS CONTINUATION: Start writing the body directly. Do NOT write meta-commentary like "This paper will discuss..." or "The body is organized to...". Just start the analytical narrative smoothly following the provided introduction.
2. AUTHORITATIVE TONE: Write in the third-person as a confident subject matter expert. Never mention that this was compiled by AI assistants, bots, or users. 
3. WORD LIMIT: Maximum of 5000 words.
4. INLINE CITATIONS: You must weave facts from the <CONVERSATION_HISTORY> into the text. Every time you state a fact, metric, or insight from a source, you must cite it immediately at the end of the sentence using square brackets []. Example: "Cloud adoption in LATAM has increased by 15% [IMARC Group LATAM - Software as a Service Market]."
5. NO SOURCE SUMMARIES IN BODY: End the body text with a strong, analytical conclusion paragraph. DO NOT create "Endnotes", "Selected Citations", or summary lists of sources at the bottom of the body. 

<AUDIENCE_SCHEMA>
{Audience_schema} 
</AUDIENCE_SCHEMA>

CRITICAL AUDIENCE ADAPTATION RULES:
- You must dynamically adapt the structure, vocabulary, and depth of the report to strictly match the schema above.
- If Role is EXECUTIVE: Lead with strategic impact, keep it high-level.
- If Role is TECHNICAL/ACADEMIC: Preserve complex methodologies, data, and structural integrity.
- If Knowledge is LOW: Explain concepts from first principles; avoid unexplained jargon.

FINAL OUTPUT REQUIREMENT:
You must also output a separate 'final_draft_sources' list. This list must ONLY contain the sources you actually cited in the body. Format each item exactly like this:
Title of Source :: Source_Quality_Rank :: URL
"""


    CREATE_LATEX_FILE_PROMPT = """ Your TASK: 
- You are an expert report compiler translating research report contents into flawless LaTeX code.
- You are given all the contents of a research paper that are to be used and you are tasked with converting that into a LATEX relevant .tex format code. 
- You will be given title, introduction, body, URL sources as content for you to convert it into latex format of .tex.


<TOPIC>
{topic}
</TOPIC>
 
<INTRO>
{intro}
</INTRO>

<BODY>
{body}
</BODY>

<SOURCES>
{sources}
</SOURCES>

""" + r"""

**************************** LATEX TEMPLATE YOU SHOULD BE FOLLOWING: ****************************
\documentclass{{article}}  

\usepackage[english]{{babel}}

\usepackage[letterpaper,top=2cm,bottom=2cm,left=3cm,right=3cm,marginparwidth=1.75cm]{{geometry}}

\usepackage{{amsmath}}
\usepackage{{graphicx}}
\usepackage[colorlinks=true, allcolors=blue]{{hyperref}}

\title{{Your Paper}}
\author{{You}}

\begin{{document}}
\maketitle

\section{{Introduction}}

Your introduction goes here! Simply start writing your document.

\section{{}}

\subsection{{}}

Simply use the section and subsection commands, as in this example document! 

\subsection{{How to add Tables}}

Use the table and tabular environments for basic tables --- see Table~\ref{{tab:widgets}}, for example. 


\subsection{{How to add Lists}}

You can make lists with automatic numbering \dots

\begin{{enumerate}}
\item Like this,
\item and like this.
\end{{enumerate}}
\dots or bullet points \dots
\begin{{itemize}}
\item Like this,
\item and like this.
\end{{itemize}}

\subsection{{How to write Mathematics}}

\LaTeX{{}} is great at typesetting mathematics. Let $X_1, X_2, \ldots, X_n$ be a sequence of independent and identically distributed random variables with $\text{{E}}[X_i] = \mu$ and $\text{{Var}}[X_i] = \sigma^2 < \infty$, and let
\[S_n = \frac{{X_1 + X_2 + \cdots + X_n}}{{n}}
      = \frac{{1}}{{n}}\sum_{{i}}^{{n}} X_i\]
denote their mean. Then as $n$ approaches infinity, the random variables $\sqrt{{n}}(S_n - \mu)$ converge in distribution to a normal $\mathcal{{N}}(0, \sigma^2)$.


\subsection{{How to add Citations and a References List}}

Here is a sentence where I want to cite my first source \cite{{smith2023}}. And here is another point that needs a different citation \cite{{jones2024}}.


\begin{{thebibliography}}{{99}}

\bibitem{{smith2023}}
Smith, J. (2023). \textit{{A great book on LaTeX}}. Tech Publisher.

\bibitem{{jones2024}}
Jones, M., \& Doe, A. (2024). "Why manual citations are sometimes faster." \textit{{Journal of Typesetting}}, 12(3), 45-60.

\end{{thebibliography}}

\end{{document}}

**************************** LATEX TEMPELATE ENDS HERE ****************************
""" + """
EXPLICIT_INSTRUCTIONS:
    CRITICAL: TEMPELATE RELATED NOTES: 
    ** You are not allowed to introduce any more libraries except the ones already present in the tempelate, the tempelate explains different kinds of subsection styles(with instructions on how to use them), you should be dynamically adapting and reason about which one to choose on your own, please use the source references library as mentioned in the tempelate instructions. 
    ** INTRODUCTION AND RELATED SECTIONS ARE ALREADY SELF-EXPLANATORY, USE PROPERLY DIVIDED SUBSECTIONS THOUGH THE PROVIDED BODY SHOULD ALREADY BE FOLLOWING THAT FORMAT, MAKE SURE TO BE AS CLEAN AND PRECISE AS POSSIBLE.
    ** Content: Replace all template placeholders with the provided summary text, structuring it purely with \section and \subsection tags.
    ** Convert the provided sources into \bibitem{{key}} bibliography entries and insert matching \cite{{key}} markers seamlessly into the prose.
    
    NOTE: 
    ** You are not allowed to change the internal contents and wordings you will be provided, just try to create the code in executable format that can be directly uploaded to overleaf to compile. 
    
    CRITICAL: ** Following is the information for the targeted audience of this report, please try to use this information strictly to refine your output: {Audience_schema}
"""

    LATEX_REPORT_IMPROVEMENT_PROMPT = """
Improvement task: 

- This is the latest error obtained in trying to run the report generated earlier by you: {Latest_error}
- History of previous errors: {history_of_errors}
- Following is the latex (.tex) formatted file generated by you:
<LATEX FILE CODE STARTS AFTER THIS LINE>

{latex_file_code}

</LATEX FILE CODE ENDS BEFORE THIS LINE>

EXPLICIT_INSTRUCTIONS:
    CRITICAL: 
    ** Your task is to refine the current code with respect to errors to generate a better codefile making sure it is absolutely flawless in order to be compiled. 
    ** Remember that the file is stored in a (.tex) format.
"""
    return (STRUCTURED_INPUT_message, ANALYST_CREATOR_PROMPT, GENERATE_QUESTIONS_PROMPT, SEARCH_QUERY_EXPERT_PROMPT, EXPERT_ANSWER_PROMPT, 
            EXPERT_RANK_SOURCES_PROMPT, CREATE_INTRO_PROMPT, CREATE_BODY_AND_SOURCES_PROMPT, CREATE_LATEX_FILE_PROMPT, 
            LATEX_REPORT_IMPROVEMENT_PROMPT) 
