# Agentic_Research_Team

A hierarchical, multi-agent research pipeline built with [LangGraph](https://python.langchain.com/docs/langgraph). This system dynamically provisions parallel AI analysts to research a topic, conduct simulated expert interviews, compile a comprehensive technical report, and self-heal LaTeX compilation errors before deterministically committing the final paper to Overleaf.

**My main motivation for this project was to do a case study in AI Platform Engineering and an attempt to make agentic workflows as deterministic as possible with minimal user interaction. The goal was not to create a fully autonomous research system, but to experiment with designing controllable, modular, and fault-tolerant LLM pipelines with minimal user intervention.**

#### Tech Stack

[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-success)](https://www.langchain.com/langgraph)
[![gpt-5-nano](https://img.shields.io/badge/LLM-gpt--5--nano-412991?logo=openai)](https://openai.com)
[![gpt-4o-mini](https://img.shields.io/badge/LLM-gpt--4o--mini-412991?logo=openai)](https://openai.com)
[![Tavily](https://img.shields.io/badge/Search-Tavily%20API-00B4B6)](https://tavily.com)
[![Pydantic](https://img.shields.io/badge/Validation-Pydantic-e92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![uv](https://img.shields.io/badge/Environment-uv-purple)](https://github.com/astral-sh/uv)
[![pdflatex](https://img.shields.io/badge/Compilation-pdflatex%20(Local)-3D6117?logo=latex&logoColor=white)](https://www.tug.org/applications/pdftex/)
[![Overleaf](https://img.shields.io/badge/Integration-Overleaf-47A141?logo=overleaf&logoColor=white)](https://www.overleaf.com/)
[![Bash](https://img.shields.io/badge/Scripting-Bash-4EAA25?logo=gnu-bash&logoColor=white)](https://www.gnu.org/software/bash/)
[![Git](https://img.shields.io/badge/Version%20Control-Git-F05032?logo=git&logoColor=white)](https://git-scm.com/)
[![LangSmith](https://img.shields.io/badge/Development-LangSmith-0072C6)](https://smith.langchain.com/)

**KEYWORDS:**  parallel sub-graphs, self-healing loop, human-in-the loop checkpoints, dynamic summarization middleware, retry policies, audience modelling, conditional re-routing and web_search functionality.

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

**NOTE ON TEST RESULTS & DEMOS:** 
Check out the `demo_and_tests/` directory for full execution logs, generated markdown files, and compiled PDFs across various test settings. Notice that the raw generated body text is 100% unique and sequentially structured; any section repetition occurs exclusively inside the final LaTeX compilation artifacts due to full-file code regeneration. Video demonstration: [YouTube Execution Run](https://youtu.be/3aU622zTymY).

**💡 Note on Model Capacity (`gpt-5-nano`) & LaTeX Generation:**  
The entire pipeline was benchmarked strictly using **`gpt-5-nano`** to evaluate nano-scale model capabilities on complex multi-agent orchestration. While `gpt-5-nano` successfully produces rich, highly structured domain analysis, lightweight models remain sensitive to long-context LaTeX syntax serialization. Any downstream PDF issues (such as math-mode escapes, truncations, or section duplication during file regeneration) are strictly isolated to the typesetting layer and do not reflect failures in the core reasoning or content generation logic.

## Architecture & Workflow

The architecture splits into a **parent graph** concerned with orchestration and compilation of the research and multiple parallel **sub-graphs** concerned with targeted research.

### 1. Preparation Phase
* **Input Structuring:** Accepts raw user prompt about the topic and optional target audience details(defaults applied via Pydantic). Sets max number of analysts to a default value of 4.
* **Analyst Generation:** Uses an analyst schema to dynamically generate unique domain-specific analysts based on the topic.
* **Human-in-the-Loop (HITL):** Uses LangGraph interrupts and conditional routing to pause execution. The user can optionally review and provide feedback to revise the analyst team before parallel execution begins.

### 2. Research Phase (Parallel Sub-Graphs): 
*   **Dynamic Interviews:** Each analyst generates detailed questions for an expert using conversation history and their specific domain instructions. 
*   **Context Management Middleware:** If an interview exceeds 5,000 words, a dynamic summarization middleware compresses older conversation history, preventing context-window overflow and reducing token drift.
*   **Expert Search & Query Optimization:** To improve factual grounding, the "Expert" generates a detailed search query to inform their answer. A specialized node dynamically modifies and trims the query to comply with Tavily Search API character limits (< 400 characters).
*   **Source Ranking:** The Expert answers the analyst, providing URLs, and explicitly ranks the retrieved context as `good`, `moderate`, or `unfavourable` to improve source quality assessment.
*   **State Reducers:** Upon interview conclusion (max 5 turns or a concluding "thank you"), resources and conversation histories are passed back to the global state using LangGraph reducers (`Annotated[list, add]`).

### 3. Compilation Phase
*   **Content Compilation:** Drafts the technical report (Intro, Body, References). It explicitly weighs `good` ranked sources higher for better factual integrity. 
*   **LaTeX Generation:** Segregated from content generation to save reasoning tokens. Uses `gpt-4o-mini` (or `gpt-5-nano`) to translate the compiled markdown/text into raw `.tex` code, saving to a local temporary file to avoid passing massive strings through the global state.
*   **Self-Healing Code Loop:** A Python `subprocess` runs `pdflatex` locally. If compilation fails, the workflow isolates the exact error logs (stored in `temp_latex_validation`) and loops back to the LLM to patch the code. (Max 5 retries).
*   **Deterministic Overleaf Commit:** A final HITL checkpoint requests user confirmation. Once approved, a deterministic bash script handles the `git push` to an Overleaf repository, bypassing the need for a non-deterministic MCP server.

## Key Technical Highlights

*   **Average Completion Time:** ~10-12 minutes `(depending on user response time, the number of HITL revision cycles, and any LaTeX refinement iterations).`
*   **Average Cost / Token Efficiency:** $0.085 - 0.1 /350-450k tokens per run `Entire pipeline executed using gpt-5-nano.`
*    **Map-Reduce Architecture:** Utilizes LangGraph's `Send` API to dynamically spawn an arbitrary number of domain-specific analysts that operate completely in parallel.
*   **Self-Healing Code Compilation:** Automated conditional routing checks LaTeX compilation logs, filtering out raw stdout noise to feed the LLM isolated failure lines—reducing reasoning token usage.
*   **Robust Retry Policies:** Custom retry handlers tailored exclusively for network drops, API timeouts, and OpenAI/Tavily rate limits, preventing pipeline collapse during high-concurrency map-reduce phases.
*   **Hierarchical State Management:** Sub-graphs maintain isolated local states. This prevents the compounding state bloat that typically plagues complex LangGraph applications.

## Design Trade-offs
*   **Deterministic Git vs. MCP Server:** Integrated Overleaf via bash scripts rather than an LLM-driven MCP terminal. While less "agentic," it guarantees deterministic code preservation and avoids catastrophic git errors by the LLM. 
*   **Local LaTeX Validation:** Requires a local LaTeX engine installation which increases environment footprint, but allows for free, unlimited, and fast compilation checks without relying on a paid external API.
*   **Source Ranking vs. Filtering:** Currently, all sources (even `unfavourable` ones) are passed to the compiler but weighted differently. A future optimization could outright drop bad sources during the interview phase to save expert-node reasoning tokens.
*   **State Memory:** No cross-session LangGraph `MemoryStore` is implemented yet, as the current goal is stateless, highly objective research generation rather than a personalized assistant.
*   **Regenerate LaTeX code completely:** The original implementation is working to regenerate the code file despite the node acting as a code patcher, this consumes a significant number of tokens and could be optimized further. More details in future work section.
  NOTE: one more thing I noticed was that since I provided a more focused/strict latex template most of the errors can be specified in prompts which can directly restrict the LLM to generate a good latex code and the fact that for the current case mostly missing $ insert in handling urls was the main issue but I still relied on full code generation since we mostly want latex template flexibility time to time.
*  **Content Synthesis vs. LaTeX Translation Artifacts:** Empirical inspection of intermediate outputs (available in `demo_and_tests/`) confirms that the core multi-agent research pipeline and markdown body generation (`CREATE_BODY_AND_SOURCES_PROMPT`) produce completely clean, non-redundant, and unique content across all topics. Duplication issues are strictly isolated to the downstream **LaTeX Translation & Self-Healing Loop**. When translating long markdown documents into raw `.tex` code or re-generating full `.tex` files to fix compilation errors, LLM context drift occurs during syntax conversion. This clearly separates **Multi-Agent Orchestration (Successful)** from **Code Syntax Translation (Target for Diff/Patching)**.

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
export PYTHONDONTWRITEBYTECODE=1
export PATH="/Library/TeX/texbin:$PATH"
uv run --active langgraph dev --no-reload
```
## Troubleshooting

- **Environment variables not loading:** Ensure the file is named `.env` and remove `.env.example`.
- **Overleaf sync issues:** Verify your Git integration token and the project ID configured in `scripts/`.
- **LaTeX errors:** Ensure `pdflatex` is installed and available in your `PATH`.
- **Version mismatch:** There can be a possibility of mismatch between pydantic versions or Typeddict importing syntax depending on which python version you run, for that case I would recommend using python versions around 3.11.
- **Warnings:** If anyone is running this kind of project for first time then I would definitely try to ignore the pydantic deserializing warning initially since it is just a deserialzing issue when we receive an empty/none value in state where we have define a strict schema.

## Future Directions
* **Adversarial Multi-Agent Verification:** Introduce a dedicated adversarial "Critic" node. Instead of linear synthesis, the Analyst (Generator) and Critic (Discriminator) will engage in a closed-loop debate. Claims that fail the Critic's stress test are dropped before reaching the global compiler, aiming to reduce hallucinations to a good extent.

* **Targeted Code Refinement (Diff/Patch):** Currently, the self-healing loop feeds the entire .tex document back to the model. Transitioning to a diff-based patching system could save up to 15,000 tokens per loop.

* **RAG Tool Node integration:** Allow users to upload seed PDFs or specific source URLs into the running memory, anchoring the web search to highly specific literature.

* **Heterogeneous LLM Routing:** Utilize different models (e.g., Claude 3.5 Sonnet for LaTeX coding, GPT-4o for content synthesis) based on task-specific strengths.

* **Degradation Fallbacks:** Implement hierarchical fallback nodes that gracefully degrade the output (e.g., dropping LaTeX compilation and returning markdown) if API limits or terminal errors occur.

* **Add a URL Checker:** To further optimize the context window, we can introduce a URL checker at the web_search node where we retrieve the URLs and only filter out those for which we are actually receiving proper content since the context is currently generated with help of tavily api which uses LLM in background.

* **Targeted AST / Diff Patching for LaTeX:** Transition from regenerating full `.tex` files during self-healing loops to AST-based or unified diff patching. Since the core content synthesis is proven to be clean and non-redundant, operating at the diff level will eliminate LLM attention drift (preventing duplicated sections) and save up to 15,000 reasoning tokens per self-healing iteration.

* **Containerized LaTeX Runtime:** Package `pdflatex` and environment dependencies into a minimal Docker container to eliminate host-level setup and improving reproducibility across platforms.

## Acknowledgments:
* I took some references for schema design of analysts from the langgraph foundational course.
* **Note on AI Usage:** I designed the workflow and state graphs for this project myself, and I used Gemini 2.5 Flash(extended thinking) as a pairing partner to iron out some Bash script edge cases (starting 4 lines) and clean up the Python string extraction logic(in latex compilation node for sanitizing meta information from llm response inside latex code).
* **Additonal AI usage:** In refining the compilation node as well -> my approach was to use pydantic base model but output were getting noisy so Gemini 2.5 Flash(extended thinking) recommended using a raw output and suggested to parse it accordingly.
* **Additonal AI usage:** In structuring the README and proper presentation of the project I have taken assistance of Gemini 2.5 Flash(extended thinking).
* **Additonal AI usage:** In structuring the CITATION.cff file.

This project focuses on engineering patterns for agentic systems rather than building a production-ready research platform. Many design decisions were made to explore reliability, debugging, and workflow control within a limited development timeframe. (20 days)

## Author

**Garveet Jain**

M.Sc. Machine Learning and Statistics
Uppsala University (Expected graduation: 2027)

LinkedIn:
https://www.linkedin.com/in/garveetjain/

GitHub:
https://github.com/Jaingarveet
