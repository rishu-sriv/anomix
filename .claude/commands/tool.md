# /tool

Add a new LangChain tool to the appropriate domain tools file.

## Usage

`/new-tool <domain> <tool_name>`

Example: `/new-tool risk get_var_metrics`

## What this does

Add a new `@tool`-decorated function to `src/tools/<domain>_tools.py` following the project pattern.

## Tool template

```python
@tool
def <tool_name>(
    param1: Annotated[str, "Clear description of param1"],
    param2: Annotated[Optional[str], "Clear description of param2; what happens if omitted"] = None,
) -> Dict[str, Any]:
    """
    One-sentence summary of what this tool does.

    USE WHEN: <specific user queries or scenarios where this tool is the right choice>

    RETURNS: <what fields are in the response and what they mean>
    """
    tenant_id = get_tenant_id()
    store = PulseIqStore()
    # implementation
    return {"success": True, "data": ...}
```

## Rules

- Import only from `src.store`, `src.utils.context`, and stdlib — no business logic in tools
- Tool names must be unique across all tool files in the domain
- Add the new tool to the worker's tool list in `src/agents/<agent_id>.py`
- Financial values returned must be Python `float` (serializable) — Decimal → float at tool boundary
