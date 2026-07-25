# Run Results & Execution Trace

This directory contains artifacts and screenshots from a single successful execution of the Agentic Research Team pipeline.


`INPUT TOPIC: Correlation Between Attention Span and Mental Health Issues: A 2026 Synthesis for a Broad Audience`

The run demonstrates:
- Dynamic analyst generation
- Parallel multi-agent research execution
- LangGraph state management and reducers
- Expert interview workflows
- LaTeX generation and self-healing validation
- Final report compilation pipeline

---

## 1. LangGraph Execution Trace

The following trace shows the complete workflow execution across the parent graph and parallel research subgraphs.

Key observations:
- Parent graph orchestration
- Parallel analyst execution
- Conditional routing
- Compilation and validation stages

<img width="466" height="515" alt="Trace" src="https://github.com/user-attachments/assets/02e3a3f4-fd56-4a14-8d23-a5170655100f" />

---

## 2. State Management Examples

Examples of intermediate LangGraph states captured during execution.

The states demonstrate:
- Analyst generation output
- Research context accumulation
- Reducer-based state merging
- Information flow between subgraphs and parent graph

<img width="581" height="441" alt="state examples" src="https://github.com/user-attachments/assets/83875d41-cdba-4cea-97f1-61a8a760e7d3" />

---

## 3. Parallel Research Execution

The pipeline dynamically provisions multiple analyst subgraphs which execute concurrently.

This run demonstrates:
- Independent domain-specific analysts
- Concurrent expert interviews
- Parallel web research workflows
- Aggregation of results after completion

<img width="1003" height="735" alt="Parallel execution showing" src="https://github.com/user-attachments/assets/c1c85e23-3f11-4d91-8d1b-34aa1f1158cf" />

---

## 4. LaTeX Self-Healing Validation Loop

The generated LaTeX document is automatically compiled locally using `pdflatex`.

If compilation fails:
1. Error logs are extracted
2. Relevant failure information is passed back to the LLM
3. The LaTeX code is repaired
4. Compilation is retried

The screenshot below shows the validation loop successfully detecting and resolving compilation issues.

<img width="769" height="860" alt="Proof of working of latex validation" src="https://github.com/user-attachments/assets/ea6bef82-6b52-4936-8f83-2d045462a786" />


---

## 5. Generated Output

The final generated technical report from this run can be found as output_1 in test_1
`NOTE: The output generated in this case contains an edge case which might be addressed in future works`
* **State Deduplication & Sequence Mapping:** While the system dynamically generates unique domain analysts to prevent redundant interviews, using `Annotated[list, add]` for map-reduce state aggregation introduces a risk of content duplication. Because the global state blindly appends interview outputs, the compilation node occasionally receives overlapping content without strict sequential awareness.
* Sections 4, 6, 8, and 10 are identical duplicate text ("A practical, implementable harmonization and integration plan").
* Sections 5, 7, and 9 are identical duplicate text ("Practical implications: concrete recommendations...").
