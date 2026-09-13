# AI Agent Project Specification

## 1. Project Purpose

This project is a local AI Agent running on a Windows PC.

The Agent uses a local LLM to:

- understand user requests
- determine whether a Tool is necessary
- discover suitable existing Tools
- execute one or more Tools
- identify missing capabilities
- support the creation of new Tools when necessary

The project is intended to be an AI-assisted Tool development system rather than a fully autonomous software development system.

Human approval remains important for significant changes.

---

## 2. Current Environment

Target environment:

- OS: Windows
- GPU: NVIDIA RTX 3060 12GB
- Python: 3.14.x
- Python environment: `.venv`
- LLM runtime: Ollama
- Current LLM: Qwen3 8B
- Agent implementation: Python
- Future integration: Node-RED
- Version control: Git

The project should remain usable in the current local environment unless there is a clear reason to change it.

---

## 3. Core Design Principles

### 3.1 Do not rely on conversation memory as the project specification

The Agent must not assume that previous conversations contain the authoritative project design.

Persistent project files are the source of truth.

Important design decisions should be recorded in project files.

### 3.2 Existing Tools should be checked before creating new Tools

Before creating a new Tool, the Agent should:

1. inspect the Tool Registry
2. search for existing Tools with similar capabilities
3. determine whether an existing Tool can satisfy the request
4. determine whether multiple existing Tools can be combined
5. only then consider creating a new Tool

### 3.3 The Agent should not arbitrarily change the project architecture

The Agent may propose architectural changes.

Significant architectural changes require human approval.

Examples:

- changing the Tool directory structure
- adding a new top-level Tool category
- changing the Registry format
- changing the Agent execution architecture
- changing the project specification

### 3.4 Tool creation should be treated as a controlled process

A new Tool should not simply be generated and immediately trusted.

The intended process is:

User request
→ requirement analysis
→ existing Tool search
→ Tool design
→ human approval when appropriate
→ implementation
→ validation
→ Registry registration
→ testing
→ Git commit

---

## 4. Tool Organization

Tools should be organized by functional category.

The current intended structure is:

```text
tools/
├── system/
├── file/
├── image/
├── audio/
├── network/
├── ai/
└── node_red/

## 5. Tool Hierarchy

Tools may use a hierarchy such as:

category/
    subcategory/
        tool.py

Example:

tools/
└── system/
    └── gpu/
        └── gpu_status.py

The hierarchy exists primarily to organize and discover Tools.

The Agent should not create unnecessarily deep directory structures.


## 6. Tool Registry

The Agent will maintain a Tool Registry describing available Tools.

The Registry should contain enough information for the Agent to understand what a Tool can and cannot do.

A Tool entry should contain at least:

- name
- category
- subcategory when applicable
- description
- keywords
- input parameters
- expected output
- risk level
- implementation reference

Example:

{
  "name": "get_gpu_status",
  "category": "system",
  "subcategory": "gpu",
  "description": "GPUの基本状態を取得する。GPUモデル、温度、使用率、VRAM使用量を取得できる。",
  "keywords": [
    "GPU",
    "グラボ",
    "VRAM",
    "温度",
    "使用率"
  ],
  "risk": "low"
}

The exact Registry format may change during development.


## 7. Tool Discovery

The Agent should not always assume that a single Tool corresponds directly to a user request.

The Agent should consider:

1. whether a Tool is necessary
2. which category is relevant
3. which existing Tools are relevant
4. whether one Tool is sufficient
5. whether multiple Tools should be combined
6. whether the required capability does not currently exist

For a small number of Tools, the Agent may inspect all Tools in the relevant category.

As the number of Tools grows, a search mechanism may be introduced.

Possible future search methods include:

- category filtering
- keyword search
- semantic search
- embeddings

The final search mechanism has not yet been fixed.


## 8. Ambiguous Requests

The Agent should be able to handle requests where the exact information or operation is not specified.

Example:

User:

"GPUのデータを表示して"

The Agent should interpret this as a request for relevant GPU information rather than assuming a single specific metric.

The Agent should consider available GPU-related capabilities such as:

- GPU model
- temperature
- utilization
- VRAM usage
- power usage
- clock information
- running processes

The Agent should not invent capabilities that do not exist.

If additional information can be obtained but no corresponding Tool exists, the Agent may identify this as a missing capability.


## 9. Missing Capabilities

If an existing Tool cannot satisfy a request, the Agent should distinguish between:

### A. Existing Tool can satisfy the request

Use it.

### B. Multiple existing Tools can satisfy the request

Plan and execute the required Tools.

### C. A new Tool is required

Do not immediately assume that a new Tool should be created.

First determine whether the required capability can reasonably be implemented using the current environment or existing systems.

If a new Tool is appropriate, the Agent may create a Tool proposal.


## 10. Tool Builder

The Tool Builder is intended primarily as a Tool development support system.

It should assist with:

- identifying missing capabilities
- proposing Tool specifications
- selecting an appropriate category
- proposing a directory location
- generating implementation code
- generating Registry metadata
- generating tests
- validating the new Tool

The Tool Builder should not initially be considered a fully autonomous software developer.

Human review remains part of the intended workflow.
## 11. Validation

Before a newly created Tool becomes an available Tool, the project should eventually validate:

- directory location
- naming
- Registry entry
- required metadata
- Python syntax
- Tool interface
- expected input/output
- basic execution
- potential destructive behavior

A future Validator Tool should automate as many of these checks as practical.


## 12. Safety

Tools that can modify or destroy user data should be treated as higher risk.

Examples:

- deleting files
- moving large numbers of files
- overwriting files
- executing arbitrary programs
- modifying system settings
- external communication

Such operations should eventually support confirmation or an approval mechanism.

The Agent should prefer inspection and simulation before destructive execution when practical.


## 13. Git

Git is used to preserve project history and provide recovery from incorrect Agent changes.

Significant changes should be committed.

The Agent should eventually be able to inspect:

git status

git diff

before changes are accepted.

Automatic commits should not initially be assumed to be safe.

Human approval may be required before committing significant Agent-generated changes.


## 14. Current Development Status

Completed:

- Git repository initialized
- Python virtual environment created
- Ollama installed
- Ollama command confirmed
- Qwen3 8B tested
- Python Agent connected to Ollama
- Basic Tool Calling implemented
- Initial GPU Tool implemented using test data

Not yet implemented:

- Tool Registry
- Tool category structure
- Tool discovery system
- Real GPU information retrieval
- Multiple Tools
- Tool validation
- Tool Builder
- Node-RED integration
- automated Tool testing
- semantic Tool search


## 15. Current Development Priority

Development should proceed approximately in this order:

1. Create Tool Registry
2. Introduce Tool categories
3. Make Agent read the Tool Registry
4. Implement basic Tool discovery
5. Replace fake GPU data with real GPU information
6. Add a second Tool
7. Test Tool selection and multi-Tool execution
8. Improve Tool discovery
9. Integrate Node-RED
10. Develop Tool Builder
11. Develop Validator
12. Improve autonomous Tool development capabilities

This order is not absolute.

The architecture may be revised when practical testing reveals weaknesses.


## 16. Design Status

The following concepts are currently under development and should not be treated as permanently fixed:

- exact Tool Registry format
- exact directory hierarchy
- semantic search implementation
- number of Tool categories
- Tool Builder implementation
- Validator implementation
- level of Agent autonomy
- Node-RED integration method
- final LLM model selection

When implementation experience conflicts with this specification, the specification should be reviewed rather than silently ignored.