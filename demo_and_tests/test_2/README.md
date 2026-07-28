# Run Results & Execution Trace

This directory contains artifacts and screenshots from the second successful execution of the Agentic Research Team pipeline.

`INPUT TOPIC: Quantum Computing in Cryptography: Post-Quantum Migration Strategies, Risk Assessment, and Enterprise Preparedness for Critical Infrastructure`

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

<img width="774" height="864" alt="trace" src="https://github.com/user-attachments/assets/dcbe7d75-65ca-4dd1-b621-6101bf043d6f" />

---

## 2. State Management Examples

Examples of intermediate audience schema generated during execution.

The states demonstrate:
- input_structuring node output
- Context accumulation
- State merging

<img width="777" height="856" alt="structure audience" src="https://github.com/user-attachments/assets/faa36caf-9c27-4f13-81e1-96bd090820b5" />

<img width="1228" height="864" alt="start input" src="https://github.com/user-attachments/assets/ac3530cd-2180-4399-ad61-da0d06bc1362" />

---

## 3. Parallel Research Execution

The pipeline dynamically provisions multiple analyst subgraphs which execute concurrently.

This run demonstrates:
- Independent domain-specific analysts
- Concurrent expert interviews
- Parallel web research workflows
- Aggregation of results after completion

<img width="764" height="869" alt="parallel" src="https://github.com/user-attachments/assets/14ff6693-7824-458f-9587-f119dcb9c2eb" />

---

## 4. LaTeX Self-Healing Validation Loop

The generated LaTeX document is automatically compiled locally using `pdflatex`.

If compilation fails:
1. Error logs are extracted
2. Relevant failure information is passed back to the LLM
3. The LaTeX code is repaired
4. Compilation is retried

The screenshot below shows the validation loop successfully detecting and resolving compilation issues.


<img width="658" height="865" alt="self healing" src="https://github.com/user-attachments/assets/87ce58d0-e02e-43b9-ac29-b9d0909c0f75" />


---

## 5. Generated Output

The final generated technical report from this run can be found as output_2 in test_2


