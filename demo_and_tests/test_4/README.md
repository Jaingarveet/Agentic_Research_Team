
## 4. LaTeX Self-Healing Validation Loop

The generated LaTeX document is automatically compiled locally using `pdflatex`.

If compilation fails:
1. Error logs are extracted
2. Relevant failure information is passed back to the LLM
3. The LaTeX code is repaired
4. Compilation is retried

The screenshot below shows the validation loop successfully detecting and resolving compilation issues.
