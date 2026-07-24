# Agentic_Research_Team

A hierarchical, multi-agent research pipeline built with [LangGraph](https://python.langchain.com/docs/langgraph). This system dynamically provisions parallel AI analysts to research a topic, conduct simulated expert interviews, compile a comprehensive technical report, and self-heal LaTeX compilation errors before deterministically committing the final paper to Overleaf.

**My main motivation for this project was to do a case study in AI Platform Engineering and an attempt to make agentic workflows as deterministic as possible with minimal user interaction.**

**KEYWORDS:**  parallel sub-graphs, self-healing loop, human-in-the loop checkpoints, dynamic summarization middleware, retry policies, audience modelling, conditional re-routing and web_search funcitonality.

<p align="center">
  <img width="600" alt="LangGraph Architecture Diagram" src="https://github.com/user-attachments/assets/25e92393-95cb-4928-8e9d-cc96d981bb20" />
</p>

## Table of Contents
- [Architecture & Workflow](#-architecture--workflow)
- [Key Technical Highlights](#-key-technical-highlights)
- [Design Trade-offs](#-design-trade-offs)
- [Getting Started](#-getting-started)
- [Future Directions](#-future-directions)

## Architecture & Workflow

The architecture splits into a **parent graph** concerned with orchestration and compilation of the research and multiple parallel **sub-graph** concerened with targeted research.

### 1. Prepartion Phase
* **Input Structuring:** Accepts raw user prompt about the topic and optional target audience details(defaults applied via Pydantic). Sets max number of analysts to a default value of 4.
* **Analyst Generation:** Uses an analyst schema to dynamically generate unique domain-specific analysts based on the topic.
* **Human-in-the-Loop (HITL):** Uses LangGraph interrupts and conditional routing to pause execution. The user can optionally review and provide feedback to revise the analyst team before parallel execution begins.

### 2. Research Phase (Parallel Sub-Graphs): 
*   **Dynamic Interviews:** Each analyst generates detailed questions for an expert using conversation history and their specific domain instructions. 
*   **Context Management Middleware:** If an interview exceeds 5,000 words, a dynamic summarization middleware steps in to compress the context, preventing context-window overflow and reducing token drift.
*   **Expert Search & Query Optimization:** To maintain legitimacy, the "Expert" generates a detailed search query to inform their answer. A specialized node dynamically modifies and trims the query to comply with Tavily Search API character limits (< 400 characters).
*   **Source Ranking:** The Expert answers the analyst, providing URLs, and explicitly ranks the retrieved context as `good`, `moderate`, or `unfavourable` to combat hallucination.
*   **State Reducers:** Upon interview conclusion (max 5 turns or a concluding "thank you"), resources and conversation histories are passed back to the global state using LangGraph reducers (`Annotated[list, add]`).

### 3. Compilation Phase
*   **Content Compilation:** Drafts the technical report (Intro, Body, References). It explicitly weighs `good` ranked sources higher for better factual integrity. 
*   **LaTeX Generation:** Segregated from content generation to save reasoning tokens. Uses `gpt-4o-mini` (or `gpt-5-nano`) to translate the compiled markdown/text into raw `.tex` code, saving to a local temporary file to avoid passing massive strings through the global state.
*   **Self-Healing Code Loop:** A Python `subprocess` runs `pdflatex` locally. If compilation fails, the workflow isolates the exact error logs (stored in `temp_latex_validation`) and loops back to the LLM to patch the code. (Max 5 retries).
*   **Deterministic Overleaf Commit:** A final HITL checkpoint requests user confirmation. Once approved, a deterministic bash script handles the `git push` to an Overleaf repository, bypassing the need for a non-deterministic MCP server.

## Key Technical Highlights

*   **Average Completion Time:** `[Insert Time]`
*   **Average Cost / Token Efficiency:** `[Insert Cost ~$0.15 / 85k tokens per run]`
*   **Map-Reduce Architecture:** Utilizes LangGraph's `Send` API to dynamically spawn an arbitrary number of domain-specific analysts that operate completely in parallel.
*   **Self-Healing Code Compilation:** Automated conditional routing checks LaTeX compilation logs, filtering out raw stdout noise to feed the LLM isolated failure lines—drastically saving reasoning tokens.
*   **Robust Retry Policies:** Custom retry handlers tailored exclusively for network drops, API timeouts, and OpenAI/Tavily rate limits, preventing pipeline collapse during high-concurrency map-reduce phases.
*   **Hierarchical State Management:** Sub-graphs maintain isolated local states. This prevents the compounding state bloat that typically plagues complex LangGraph applications.

## Design Trade-offs
*   **Deterministic Git vs. MCP Server:** Integrated Overleaf via bash scripts rather than an LLM-driven MCP terminal. While less "agentic," it guarantees deterministic code preservation and avoids catastrophic git errors by the LLM. 
*   **Local LaTeX Validation:** Requires a local LaTeX engine installation which increases environment footprint, but allows for free, unlimited, and fast compilation checks without relying on a paid external API.
*   **Source Ranking vs. Filtering:** Currently, all sources (even `unfavourable` ones) are passed to the compiler but weighted differently. A future optimization could outright drop bad sources during the interview phase to save expert-node reasoning tokens.
*   **State Memory:** No cross-session LangGraph `MemoryStore` is implemented yet, as the current goal is stateless, highly objective research generation rather than a personalized assistant.


## Getting Started
### Pre-requisites
*   Python 3.10+
*   A local LaTeX distribution (e.g., TeX Live, MacTeX, or MiKTeX) for `pdflatex` validation.
*   An Overleaf account with Git integration enabled.


**environment file should look like this:**

OPENAI_API_KEY='YOUR_OPEN_AI_API_KEY'
TAVILY_API_KEY='YOUR_TAVILY_API_KEY'

**Optional for evaluation and tracing**
LANGSMITH_API_KEY='YOUR_LANGSMITH_API_KEY'
 **set tracing to true when you set up your LangSmith account**
 LANGSMITH_TRACING=true
 LANGSMITH_PROJECT= your_project_name
**Uncomment the following if you are on the EU instance:**
 #LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com

**Reproduce the code:**
- clone repo -> python environment -> env file for variables ->pip install requirements.txt -> langgraph dev


## Future Directions
* **Adversarial Multi-Agent Verification (Agentic GANs):** Introduce a dedicated adversarial "Critic" node. Instead of linear synthesis, the Analyst (Generator) and Critic (Discriminator) will engage in a closed-loop debate. Claims that fail the Critic's stress test are dropped before reaching the global compiler, theoretically driving hallucination rates to zero.

* **Targeted Code Refinement (Diff/Patch):** Currently, the self-healing loop feeds the entire .tex document back to the model. Transitioning to a diff-based patching system could save up to 15,000 tokens per loop.

* **RAG Tool Node integration:** Allow users to upload seed PDFs or specific source URLs into the running memory, anchoring the web search to highly specific literature.

* **Heterogeneous LLM Routing:** Utilize different models (e.g., Claude 3.5 Sonnet for LaTeX coding, GPT-4o for content synthesis) based on task-specific strengths.

* **Degradation Fallbacks:** Implement hierarchical fallback nodes that gracefully degrade the output (e.g., dropping LaTeX compilation and returning markdown) if API limits or terminal errors occur.
