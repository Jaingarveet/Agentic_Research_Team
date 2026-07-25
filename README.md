# Agentic_Research_Team

A hierarchical, multi-agent research pipeline built with [LangGraph](https://python.langchain.com/docs/langgraph). This system dynamically provisions parallel AI analysts to research a topic, conduct simulated expert interviews, compile a comprehensive technical report, and self-heal LaTeX compilation errors before deterministically committing the final paper to Overleaf.

**My main motivation for this project was to do a case study in AI Platform Engineering and an attempt to make agentic workflows as deterministic as possible with minimal user interaction. The goal was not to create a fully autonomous research system, but to experiment with designing controllable, modular, and fault-tolerant LLM pipelines with minimal user intervention.**

**KEYWORDS:**  parallel sub-graphs, self-healing loop, human-in-the loop checkpoints, dynamic summarization middleware, retry policies, audience modelling, conditional re-routing and web_search funcitonality.

<p align="center">
  <img width="1117" height="1408" alt="image" src="https://github.com/user-attachments/assets/5fea1390-d077-4b49-bd3a-325ffd5a77d5" />
</p>

## Table of Contents
- Architecture & Workflow
- Key Technical Highlights
- Design Trade-offs
- Getting Started
- Future Directions
- Acknowledgements

**NOTE:** Checkout the details of tests in demo_and_tests folder, it also has the final pdfs generated across different testing settings.

## Architecture & Workflow

The architecture splits into a **parent graph** concerned with orchestration and compilation of the research and multiple parallel **sub-graphs** concerned with targeted research.

### 1. Preparation Phase
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

*   **Average Completion Time:** 10 mins `(the only thing varies is how long does user takes to respond and the number of time we refine with HITL feedback in analyst creation or the latex validation towards the end)`
*   **Average Cost / Token Efficiency:** $0.085 /350-400k tokens per run `Only used gpt-5-nano for the whole architecture`
*    **Map-Reduce Architecture:** Utilizes LangGraph's `Send` API to dynamically spawn an arbitrary number of domain-specific analysts that operate completely in parallel.
*   **Self-Healing Code Compilation:** Automated conditional routing checks LaTeX compilation logs, filtering out raw stdout noise to feed the LLM isolated failure lines—drastically saving reasoning tokens.
*   **Robust Retry Policies:** Custom retry handlers tailored exclusively for network drops, API timeouts, and OpenAI/Tavily rate limits, preventing pipeline collapse during high-concurrency map-reduce phases.
*   **Hierarchical State Management:** Sub-graphs maintain isolated local states. This prevents the compounding state bloat that typically plagues complex LangGraph applications.

## Design Trade-offs
*   **Deterministic Git vs. MCP Server:** Integrated Overleaf via bash scripts rather than an LLM-driven MCP terminal. While less "agentic," it guarantees deterministic code preservation and avoids catastrophic git errors by the LLM. 
*   **Local LaTeX Validation:** Requires a local LaTeX engine installation which increases environment footprint, but allows for free, unlimited, and fast compilation checks without relying on a paid external API.
*   **Source Ranking vs. Filtering:** Currently, all sources (even `unfavourable` ones) are passed to the compiler but weighted differently. A future optimization could outright drop bad sources during the interview phase to save expert-node reasoning tokens.
*   **State Memory:** No cross-session LangGraph `MemoryStore` is implemented yet, as the current goal is stateless, highly objective research generation rather than a personalized assistant.
*   **Regenerate LaTeX code completely:** The original implementation is working to regenerate the code file despite the node acting as a code patcher, this uses a lot of token which can be optimized to a good extent. More details in future work section.
  NOTE: one more thing I noticed was that since I provided a more focused/strict latex template most of the errors can be specified in prompts which can directly restrict the LLM to generate a good latex code and the fact that for the current case mostly missing $ insert in handling urls was the main issue but I still relied on full code generation since we mostly want latex template flexibility time to time.
* **State Deduplication & Sequence Mapping:** While the system dynamically generates unique domain analysts to prevent redundant interviews, using `Annotated[list, add]` for map-reduce state aggregation introduces a risk of content duplication. Because the global state blindly appends interview outputs, the compilation node occasionally receives overlapping content without strict sequential awareness. `Checkout the edge_case_test directory inside demo_and_tests for more insights`

## Getting Started
### Pre-requisites
*   Python 3.10+
*   A local LaTeX distribution (e.g., TeX Live, MacTeX, or MiKTeX) for `pdflatex` validation.
*   `uv`
*   An Overleaf project with Git integration enabled.

## Setup

1. Clone the repository.

```bash
git clone https://github.com/Jaingarveet/Agentic_Research_Team.git
cd Agentic_research_team
```
`NOTE: (Optional) Deactivate any active base environment.`

2. Create a `.env` file in the project root.

```env
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
TAVILY_API_KEY="YOUR_TAVILY_API_KEY"

# Generate your Overleaf Git token at:
# https://www.overleaf.com/user/settings
GITHUB_TOKEN="YOUR_OVERLEAF_GIT_TOKEN"

# Optional: LangSmith
LANGSMITH_API_KEY="YOUR_LANGSMITH_API_KEY"
LANGSMITH_TRACING=true
LANGSMITH_PROJECT="your_project_name"
# LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```
3. Remove `.env.example` (present in root directory(Agentic_Research_Team)).

```bash
rm .env.example
```
4. Update the Overleaf project ID in the script under `scripts/`.

5. Install dependencies and start LangGraph.
`NOTE: this step is to be done in root repository!`
```bash
uv sync
source .venv/bin/activate
uv run --active langgraph dev
```
## Troubleshooting

- **Environment variables not loading:** Ensure the file is named `.env` and remove `.env.example`.
- **Overleaf sync issues:** Verify your Git integration token and the project ID configured in `scripts/`.
- **LaTeX errors:** Ensure `pdflatex` is installed and available in your `PATH`.
- **Version mismatch:** There can be a possibility of mismatch between pydantic versions or Typeddict importing syntax depending on which python version you run, for that case I would recommend using python versions around 3.11.
- **Warnings:** If anyone is running this kind of project for first time then I would definitely try to ignore the pydantic deserializing warning initially since it is just a deserialzing issue when we recieve an empty/none value in state where we have define a strict schema.

## Future Directions
* **Adversarial Multi-Agent Verification (Agentic GANs):** Introduce a dedicated adversarial "Critic" node. Instead of linear synthesis, the Analyst (Generator) and Critic (Discriminator) will engage in a closed-loop debate. Claims that fail the Critic's stress test are dropped before reaching the global compiler, theoretically driving hallucination rates to zero.

* **Targeted Code Refinement (Diff/Patch):** Currently, the self-healing loop feeds the entire .tex document back to the model. Transitioning to a diff-based patching system could save up to 15,000 tokens per loop.

* **RAG Tool Node integration:** Allow users to upload seed PDFs or specific source URLs into the running memory, anchoring the web search to highly specific literature.

* **Heterogeneous LLM Routing:** Utilize different models (e.g., Claude 3.5 Sonnet for LaTeX coding, GPT-4o for content synthesis) based on task-specific strengths.

* **Degradation Fallbacks:** Implement hierarchical fallback nodes that gracefully degrade the output (e.g., dropping LaTeX compilation and returning markdown) if API limits or terminal errors occur.

* **Add a URL Checker:** To further optimize the context window, we can introduce a URL checker at the web_search node where we retrieve the URLs and only filter out those for which we are actually receiving proper content since the context is currently generated with help of tavily api which uses LLM in background.

* **De-duplication issue:** Since every interview session generates a unique ID, transitioning the global state from a simple list to a key-value dictionary (mapped by interview ID) would act as a natural deduplication filter. Alternatively, inserting a lightweight, programmatic validation node immediately before compilation could parse these IDs and prune duplicate context, saving the LLM from wasting reasoning tokens on redundant data.

## Acknowledgments:
* I took some refereneces for schema design from the langgraph foundational course.
* **Note on AI Usage:** I designed the workflow and state graphs for this project myself, but I used Gemini as a pairing partner to iron out some Bash script edge cases and clean up the Python string extraction logic.
* **Additonal AI usage includes:** In refining the compilation node as well -> my approach was to use pydantic base model but output were getting noisy so gemini recommended using a raw output and suggested to parse it accordingly.


`This project focuses on engineering patterns for agentic systems rather than building a production-ready research platform. Many design decisions were made to explore reliability, debugging, and workflow control within a limited development timeframe.`

`Hi, at time of developing this project I am a student at uppsala university of graduating in 2027, my name is Garveet Jain and here are my credentials:
linkedin: www.linkedin.com/in/garveetjain/ 
github: https://github.com/Jaingarveet`
