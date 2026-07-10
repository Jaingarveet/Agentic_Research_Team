# Agentic_Research_Team
This repo contains the code of my project: Agentic_research team which is an automated multi_agent architecture built using langgraph,langchain and langsmith. Main use case is automating research analysis and report generation without loosing technical details.

Lots to do ::


Semi-final graph draft

<img width="489" height="475" alt="Screenshot 2026-07-08 at 4 25 54 PM" src="https://github.com/user-attachments/assets/27fa1a78-012a-4bb7-9cd7-12013582a02d" />

environment file should look like this: 
Required  
OPENAI_API_KEY='YOUR_OPEN_AI_API_KEY'
TAVILY_API_KEY='YOUR_TAVILY_API_KEY'

 optional, only used in Module 1, Lesson 1 once
ANTHROPIC_API_KEY='your_anthropic_api_key_here'
GOOGLE_API_KEY='your_google_api_key_here'

 Optional for evaluation and tracing
LANGSMITH_API_KEY='YOUR_LANGSMITH_API_KEY'
 uncomment to set tracing to true when you set up your LangSmith account
 LANGSMITH_TRACING=true
 LANGSMITH_PROJECT= your_project_name
Uncomment the following if you are on the EU instance:
 LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
