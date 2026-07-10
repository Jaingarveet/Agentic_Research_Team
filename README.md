# Agentic_Research_Team
This repo contains the code of my project: Agentic_research team which is an automated multi_agent architecture built using langgraph,langchain and langsmith. Main use case is automating research analysis and report generation without loosing technical details.

Lots to do ::


Semi-final graph draft

<img width="489" height="475" alt="Screenshot 2026-07-08 at 4 25 54 PM" src="https://github.com/user-attachments/assets/27fa1a78-012a-4bb7-9cd7-12013582a02d" />

**environment file should look like this:**

OPENAI_API_KEY='YOUR_OPEN_AI_API_KEY'
TAVILY_API_KEY='YOUR_TAVILY_API_KEY'

ANTHROPIC_API_KEY='your_anthropic_api_key_here'
GOOGLE_API_KEY='your_google_api_key_here'

**Optional for evaluation and tracing**
LANGSMITH_API_KEY='YOUR_LANGSMITH_API_KEY'
 **set tracing to true when you set up your LangSmith account**
 LANGSMITH_TRACING=true
 LANGSMITH_PROJECT= your_project_name
**Uncomment the following if you are on the EU instance:**
 LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com




**Future Works:** Personalize the final report creation agent to retrieve an in memory store object to get across-conversational context of the user which and agent could submit as a conclusion to the store, might need to create a rate_limit backend server as well and many more things if taken to production.
Another dynamic thing that could be added is that we let a user upload a pdf of a research paper as well (by building a RAG toolnode for that) or some sources links that allows to get a broader context rather than conducting interviews (though it also uses web_search anyways which can be also extended using wikipedia api parallely). Or we could just let the RAG be uploaded as a part of the running memory using langgraph store instead?
Might need to check for compounding increase in state_history if we let this much context in.
Personalities to expert, 
fixed expert without analyst creator that converses according to domain requirement?
