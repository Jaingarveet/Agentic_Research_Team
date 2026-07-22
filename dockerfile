FROM langchain/langgraph-api

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# want to keep texlive separate since there was a automatic dependency downgrade bug

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*      

COPY . .

RUN pdflatex --version
