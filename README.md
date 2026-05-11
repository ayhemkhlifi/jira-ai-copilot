# Jira AI Copilot

Jira AI Copilot is an AI-powered assistant designed to streamline Agile delivery by transforming meeting notes, specifications, and backlog analysis into structured Jira tickets. It uses a RAG (Retrieval-Augmented Generation) pipeline with LangGraph agents to ensure high-quality, consistent ticket generation.

## Features

- **Automated Ticket Generation**: Convert natural language notes into Jira stories, tasks, and bugs.
- **RAG-Powered Intelligence**: Uses historical Jira data and project documentation to provide context-aware suggestions.
- **Multi-Agent Pipeline**: Includes specialized agents for anomaly detection, effort estimation, and subtask generation.
- **Human-in-the-loop**: Review board for editing and approving tickets before they are pushed to Jira.
- **Jira Connect Integration**: Seamlessly integrates into the Jira UI via an iframe.

## Technology Stack

- **Backend**: FastAPI, LangGraph, LangChain, Qdrant (Vector Database).
- **Frontend**: React, Vite, Tailwind CSS.
- **LLM**: Mistral AI.
- **Deployment**: Dockerized, ready for Railway or Render.

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Jira Cloud account
- Mistral AI API Key
- Qdrant (local or cloud)

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/jira-ai-copilot1.git
    cd jira-ai-copilot1
    ```

2.  **Backend Setup**:
    ```bash
    # Create and activate virtual environment
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

    # Install dependencies
    pip install -r requirements.txt

    # Set up environment variables
    cp .env.example .env
    # Edit .env with your credentials
    ```

3.  **Frontend Setup**:
    ```bash
    cd frontend
    npm install
    ```

### Running Locally

1.  **Start the Backend**:
    ```bash
    python -m src.api.server
    ```

2.  **Start the Frontend**:
    ```bash
    cd frontend
    npm run dev
    ```

### Deployment

The project is ready for deployment as a single Docker container.

1.  **Seed Qdrant Cloud**:
    ```bash
    python seed_qdrant.py --qdrant-url "YOUR_CLOUD_URL" --qdrant-api-key "YOUR_API_KEY"
    ```

2.  **Deploy to Railway**:
    The project includes `Dockerfile` and `railway.json` for easy deployment.

## License

[MIT License](LICENSE)
