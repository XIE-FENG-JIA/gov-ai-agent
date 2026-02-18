# Tasks: 公文 AI Agent Implementation

## Phase 1: Foundation & CLI
- [x] **Task-1.1**: Initialize Python project with `pyproject.toml` and dependencies (typer, litellm, chromadb). <!-- id: task-1-1 -->
- [x] **Task-1.2**: Implement basic CLI skeleton using `typer` with a `version` command. <!-- id: task-1-2 -->
- [x] **Task-1.3**: Create `LLMProvider` abstraction to support easy switching between Ollama/Gemini. <!-- id: task-1-3 -->

## Phase 2: Knowledge Base & RAG
- [x] **Task-2.1**: Implement `KnowledgeBaseManager` using ChromaDB. <!-- id: task-2-1 -->
- [x] **Task-2.2**: Create `ingest` command to import markdown-based public doc examples. <!-- id: task-2-2 -->
- [x] **Task-2.3**: Implement semantic search function to retrieve relevant examples. <!-- id: task-2-3 -->

## Phase 3: Core Agents
- [x] **Task-3.1**: Implement `RequirementAgent` to parse user input into JSON. <!-- id: task-3-1 -->
- [x] **Task-3.2**: Implement `WriterAgent` to generate draft content based on template and retrieved examples. <!-- id: task-3-2 -->
- [x] **Task-3.3**: Implement `TemplateEngine` to map content to standard "函/公告/簽" markdown structures. <!-- id: task-3-3 -->

## Phase 4: Review & Export
- [x] **Task-4.1**: Implement `FormatAuditor` agent to check field completeness. <!-- id: task-4-1 -->
- [x] **Task-4.2**: Create `DocxExporter` to convert markdown draft to formatted `.docx`. <!-- id: task-4-2 -->
- [x] **Task-4.3**: Integrate full pipeline into `gov-ai generate` command. <!-- id: task-4-3 -->
