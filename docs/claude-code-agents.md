# Claude Code Agents: Best Practices Guide

This document explains how to effectively create and use agents in Claude Code based on our experience and the official Claude Code documentation.

## Table of Contents
- [What Are Agents?](#what-are-agents)
- [When to Use Agents](#when-to-use-agents)
- [Agent Configuration](#agent-configuration)
- [Best Practices](#best-practices)
- [Common Mistakes](#common-mistakes)
- [Our Agent Setup](#our-agent-setup)
- [References](#references)

## What Are Agents?

Agents in Claude Code are specialized AI assistants that run in **separate context windows** to handle specific tasks. They help preserve your main context window tokens while providing focused expertise.

**Key Characteristics:**
- Run in isolated context windows
- Have their own system prompts and instructions
- Can access specific tools
- Preserve main conversation context
- Enable parallel task execution

**Official Documentation:** [Claude Code Agents](https://docs.claude.com/en/docs/claude-code/agents)

## When to Use Agents

### ✅ Use Agents For:

1. **Documentation Lookups**
   - Fetching current library documentation
   - API reference queries
   - Version-specific changes
   - Example: `context7-docs` agent

2. **Specialized Domain Knowledge**
   - Platform-specific expertise (e.g., UBI/Red Hat)
   - Framework-specific patterns
   - Complex technical domains
   - Example: `ubi-redhat-expert` agent

3. **Complex Multi-Step Research**
   - Investigating multiple libraries
   - Comparative analysis
   - Architecture decisions requiring extensive research

### ❌ Don't Use Agents For:

1. **Simple, Direct Operations**
   - File reading/writing
   - Basic code modifications
   - Single MCP tool calls
   - Simple calculations

2. **General Programming Tasks**
   - Python coding (Claude handles natively)
   - Docker operations (Claude handles natively)
   - Testing and linting
   - Code reviews

3. **Every Small Task**
   - Don't over-engineer with too many agents
   - Avoid agent-for-everything antipattern

**Principle:** If Claude Code can handle it efficiently in the main context, don't create an agent for it.

## Agent Configuration

### File Structure

Agents are defined in `.claude/agents/` directory:

```
.claude/
├── agents/
│   ├── context7-docs.md
│   └── ubi-redhat-expert.md
└── settings.json
```

### Agent Definition Format

```markdown
---
name: agent-name
description: Short description (shows in agent list)
tools: Read, Write, Bash, etc.
model: inherit
---

You are the {agent-name} agent. Your job is...

## Workflow:
1. Step-by-step process
2. What to do
3. How to do it

## Auto-Trigger On:
- "Trigger phrase 1"
- "Trigger phrase 2"

## Rules:
- ✅ DO: Best practices
- ❌ DON'T: Anti-patterns
```

### Key Components

**1. Front Matter (YAML)**
```yaml
---
name: context7-docs              # Agent identifier
description: Brief description   # Shown to user
tools: Read, Write              # Available tools
model: inherit                   # Use same model as main
---
```

**2. System Prompt**
Clear instructions about the agent's role and responsibilities.

**3. Workflow**
Step-by-step process the agent should follow.

**4. Auto-Triggers** (optional)
Phrases that should automatically invoke the agent.

**5. Rules**
Do's and don'ts for the agent's behavior.

## Best Practices

### 1. Keep Agents Focused

**Good:**
```markdown
name: context7-docs
description: Fetch current documentation using Context7
```

**Bad:**
```markdown
name: super-helper
description: Does everything - docs, coding, testing, deployment
```

### 2. Minimize Agent Count

**Our Evolution:**
- Started with: 9 agents (too many!)
- Removed: 7 agents (python-developer, code-reviewer, docker-optimizer, etc.)
- Kept: 2 agents (context7-docs, ubi-redhat-expert)
- Result: More efficient, less confusion

**Lesson:** Start with 0 agents, add only when truly needed.

### 3. Use Clear Trigger Patterns

**Good Auto-Triggers:**
```markdown
## Auto-Trigger On:
- "How do I use [library]?"
- "Latest [library] API changes?"
- "[Library] breaking changes?"
```

**Why:** Makes it obvious when the agent should be used.

### 4. Preserve Context Window Tokens

**Agent Benefits:**
- Main context: Coordinates high-level work
- Agent context: Handles detailed research
- Result: Both contexts stay focused and efficient

**Token Flow:**
```
Main Context (Your work)
    ├─ Spawns Agent → Separate Context
    │                  ├─ Research
    │                  ├─ Tool calls
    │                  └─ Returns result
    └─ Receives summary (minimal tokens)
```

### 5. Document Agent Purpose

Always include in CLAUDE.md:
```markdown
## Development Practices
- When you need documentation about libraries:
  - **ALWAYS use the context7-docs agent** (configured in `.claude/agents/`)
  - Never use WebFetch for technical documentation
```

## Common Mistakes

### ❌ Mistake 1: Creating Too Many Agents

**Problem:**
```
.claude/agents/
├── python-developer.md
├── docker-expert.md
├── code-reviewer.md
├── api-developer.md
├── uv-expert.md
└── ... (9 agents total)
```

**Solution:** Claude Code already handles general programming. Only create agents for specialized domains.

### ❌ Mistake 2: Using Agents for Simple Tasks

**Problem:**
```markdown
# Spawning agent for every file read
Task: Read file X
Agent: file-reader
Result: Wasted tokens
```

**Solution:** Use direct tool calls for simple operations.

### ❌ Mistake 3: Ignoring Configured Agents

**Problem:**
- Agent exists: `context7-docs`
- Developer uses: `WebFetch` instead
- Result: Stale documentation, wasted agent config

**Solution:** Follow the configured patterns, use agents when they exist.

### ❌ Mistake 4: No Clear Documentation

**Problem:** Team doesn't know when to use which agent.

**Solution:** Document in CLAUDE.md with clear guidelines.

## Our Agent Setup

### context7-docs Agent

**Purpose:** Fetch current library/framework documentation using Context7 MCP tools.

**When to Use:**
- "How does Renovate handle `.tool-versions`?"
- "What's new in FastAPI 0.118?"
- "Show me uv configuration options"

**Why It Exists:**
- Documentation queries require separate research context
- Context7 provides up-to-date docs (better than WebFetch)
- Preserves main context for coordination

**Configuration:**
```markdown
---
name: context7-docs
description: Fetch current documentation for any library/framework using Context7
tools: Read, Write
model: inherit
---
```

### ubi-redhat-expert Agent

**Purpose:** Specialized knowledge for Red Hat UBI (Universal Base Image) and RHEL ecosystem.

**When to Use:**
- UBI-specific package management (microdnf)
- OpenShift compatibility questions
- RHEL security and compliance
- UBI vs Alpine decisions

**Why It Exists:**
- Specialized domain knowledge not general-purpose
- UBI has specific patterns and constraints
- Enterprise/RHEL ecosystem expertise

## Decision Tree: Do I Need an Agent?

```
Is this a general programming task?
├─ YES → No agent needed (Claude handles it)
└─ NO → Continue

Is this a simple, single-step operation?
├─ YES → Use direct tool/MCP call
└─ NO → Continue

Does it require specialized domain knowledge?
├─ YES → Consider creating an agent
└─ NO → Continue

Does it require extensive documentation research?
├─ YES → Use context7-docs agent
└─ NO → Handle in main context
```

## Token Efficiency Comparison

### Scenario: "How to configure Renovate for `.tool-versions`?"

**Option 1: Direct in Main Context**
```
Tokens used: ~5,000 (research + context)
Main context: Cluttered with details
```

**Option 2: Use context7-docs Agent**
```
Tokens used in main: ~500 (spawn + summary)
Tokens used in agent: ~4,500 (research)
Main context: Clean, focused on coordination
Result: More efficient overall
```

**Winner:** Agent approach for complex research.

### Scenario: "Read pyproject.toml"

**Option 1: Spawn file-reader Agent**
```
Overhead: ~1,000 tokens (agent spawn)
File read: ~200 tokens
Total: ~1,200 tokens
```

**Option 2: Direct Read Tool**
```
File read: ~200 tokens
Total: ~200 tokens
```

**Winner:** Direct tool call for simple operations.

## Migration Guide: Too Many Agents → Right-Sized

### Before (9 agents)
```
.claude/agents/
├── api-developer.md        # ❌ General programming
├── code-debugger.md        # ❌ General programming
├── code-reviewer.md        # ❌ General programming
├── context7-docs.md        # ✅ Specialized
├── docker-optimizer.md     # ❌ General programming
├── python-developer.md     # ❌ General programming
├── research-coordinator.md # ❌ Too meta
├── ubi-redhat-expert.md    # ✅ Specialized
└── uv-python-installer.md  # ❌ General programming
```

### After (2 agents)
```
.claude/agents/
├── context7-docs.md        # ✅ Documentation research
└── ubi-redhat-expert.md    # ✅ UBI/RHEL expertise
```

### Results
- ✅ Clearer when to use agents
- ✅ Less configuration maintenance
- ✅ Better token efficiency
- ✅ Claude Code handles general tasks naturally

## Testing Your Agent Setup

### 1. Ask Documentation Questions

**Test:** "How does Renovate's asdf manager work?"

**Expected:** context7-docs agent should be used automatically or proactively.

### 2. Ask General Programming Questions

**Test:** "Write a Python function to parse JSON"

**Expected:** Claude Code handles it directly, no agent needed.

### 3. Ask Specialized Questions

**Test:** "How to optimize UBI minimal image size?"

**Expected:** ubi-redhat-expert agent engages.

## References

### Official Documentation
- [Claude Code Main Docs](https://docs.claude.com/en/docs/claude-code)
- [Claude Code Agents](https://docs.claude.com/en/docs/claude-code/agents)
- [Agent SDK](https://docs.claude.com/en/docs/claude-code/sdk)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

### Related Documentation
- [Context7 MCP Server](https://github.com/context7/context7-mcp-server)
- [Claude Code GitHub](https://github.com/anthropics/claude-code)

### Internal Documentation
- [CLAUDE.md](../CLAUDE.md) - Project-specific guidelines
- [context7-docs agent](../.claude/agents/context7-docs.md) - Documentation agent config
- [ubi-redhat-expert agent](../.claude/agents/ubi-redhat-expert.md) - UBI expertise agent config

## Key Takeaways

1. **Agents are for specialized tasks**, not general programming
2. **Fewer agents is better** - start with 0, add when needed
3. **Context window preservation** is the main benefit
4. **Document your agent usage** in CLAUDE.md
5. **Follow configured patterns** - if an agent exists, use it
6. **Direct tool calls for simple operations** are more efficient
7. **Claude Code handles general programming** without agents

## Questions?

If you're unsure whether to create an agent, ask:
1. Can Claude Code handle this natively? → No agent
2. Is this a one-liner operation? → No agent
3. Does this require specialized domain knowledge? → Maybe agent
4. Will this cluttered main context significantly? → Maybe agent

**When in doubt, start without an agent.** You can always add one later if needed.

---

*Last updated: 2025-10-08*
*Based on Claude Code version: Latest*
