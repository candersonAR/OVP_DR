# Max Tools Project - Skill Development Guide

## Project Overview
This repository is for building skills/tools that wrap AnswerRocket SDK functionality. Each skill is implemented as a separate Python file in the root directory.

## Environment Setup
- Python virtual environment: `venv/`
- Key packages:
  - `answerrocket-client` - AnswerRocket Python SDK
  - `skill-framework[ui]` - Skill framework with UI preview server

## Getting Started

### Understanding the AnswerRocket SDK
To understand available SDK methods and their signatures:
1. Check existing skill files (*.py) in the root directory for usage patterns
2. Import the SDK and explore: `from answer_rocket import AnswerRocketClient`
3. Look for SDK documentation or examples in the codebase

### Understanding the Skill Framework
To understand how to structure skills:
1. Examine existing skill files to see the `@skill` decorator pattern
2. Look at `skills.txt` to see how skills are registered
3. Check imports to understand `SkillInput`, `SkillOutput`, and `SkillParameter` usage

## Skill Development Pattern

### Basic Structure
Skills follow this decorator pattern:
```python
@skill(
    name="skill_name",
    description="Description of what the skill does",
    parameters=[
        SkillParameter(
            name="param_name",
            description="Parameter description",
            required=True
        )
    ]
)
def skill_function(parameters: SkillInput) -> SkillOutput:
    # Access parameters via parameters.arguments.param_name
    # Return SkillOutput with final_prompt, narrative, visualizations, export_data
```

### Key Components
- **Client Setup:** Create `AnswerRocketClient()` instance
- **Parameter Access:** Use `parameters.arguments.param_name`
- **Error Handling:** Wrap SDK calls in try-catch blocks
- **Output:** Return structured `SkillOutput` responses

### Skill Registration
Add new skill files to `skills.txt` (one filename per line) to make them discoverable.

## Learning from Existing Code

### Finding Examples
- Look at existing `.py` files in root directory for implementation patterns
- Check how existing skills handle SDK client creation
- See how parameters are processed and validated
- Observe error handling approaches
- Study output formatting patterns

### Key Areas to Examine
- Import statements for required dependencies
- Parameter extraction from `SkillInput`
- SDK method calls and error handling
- Data processing and formatting
- `SkillOutput` construction with export data

## Development Approach
1. **Explore:** Examine existing skills to understand patterns
2. **Plan:** Identify which SDK methods to wrap
3. **Implement:** Follow existing patterns for consistency
4. **Register:** Add to `skills.txt`
5. **Test:** Verify functionality works as expected

This guide provides the foundation - refer to existing code in this repository for concrete implementation details and patterns.
