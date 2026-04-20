# LangSmith Integration Plan and Rollout

## Objectives
- Monitor agent routing and tool decisions for each chat request.
- Debug tool execution and failure points with trace spans.
- Track response accuracy using structured reviewer feedback.
- Use traces + feedback to optimize performance and quality over time.

## Architecture
- Automatic tracing layer:
  - Enable via environment variables (`LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`).
  - Captures LangChain-level model/prompt/tool internals.
- Manual observability layer:
  - Root run for each chat request (`chat.process`).
  - Child run for tool routing decision (`chat.tool_selection`).
  - Child run for selected tool execution (`chat.tool.<tool_name>`).
  - Error capture on both child and root runs.
- Accuracy feedback layer:
  - New API endpoint to submit feedback for a run (`/chat/feedback`).
  - Supports score, key, comment, metadata.

## Data Captured
- Request inputs: role, selected tool, query payload fields.
- Decision metadata: selected tool after normalization.
- Tool execution metadata: role, tool inputs, source label, response preview, duration_ms.
- Error metadata: captured exception string on tool/root runs.
- Accuracy metadata: reviewer score and optional comments.

## Implementation Steps
1. Add centralized LangSmith settings in backend config.
2. Add a resilient LangSmith tracer wrapper service with safe fallbacks.
3. Instrument chat orchestration flow with root and child runs.
4. Return trace_id in chat response for debugging and feedback linking.
5. Add feedback schema + endpoint to store response accuracy.
6. Add `langsmith` dependency.
7. Validate with focused and full test runs.

## Environment Setup
Set the following in backend `.env`:
- `LANGSMITH_TRACING=true`
- `LANGSMITH_API_KEY=<your_langsmith_api_key>`
- `LANGSMITH_PROJECT=healthcare-assistant`
- `LANGSMITH_ENDPOINT=https://api.smith.langchain.com` (optional)

## API Usage
- Chat request (existing): `POST /chat`
  - Response now includes `trace_id`.
- Feedback request (new): `POST /chat/feedback`
  - Body:
    - `run_id`: trace/run id returned by chat
    - `score`: float in [0.0, 1.0]
    - `key`: feedback metric key (default `response_accuracy`)
    - `comment`: optional note
    - `metadata`: optional object
- Analytics request (new): `GET /chat/analytics/low-score-tools`
  - Query params:
    - `key`: feedback metric key
    - `threshold`: include scores less than or equal to threshold
    - `limit`: max feedback items to inspect

## Runtime Safeguards
- Empty model responses are normalized to a safe fallback message to avoid blank assistant outputs.
- Trace outputs include duration metadata for both tool span and full chat request.

## Validation Checklist
- Chat call returns non-empty `trace_id` when LangSmith env vars are set.
- Trace in LangSmith includes:
  - `chat.process`
  - `chat.tool_selection`
  - `chat.tool.<tool_name>`
- Tool errors are visible in trace with error text.
- Feedback API accepts valid payload and appears in LangSmith run feedback.
- Analytics API returns grouped low-score counts and average score by tool.

## Optimization Workflow
1. Filter traces by tool and role to identify slow/failing paths.
2. Use response preview + source label mismatches to catch routing errors.
3. Aggregate feedback scores by tool/intent to find weak intents.
4. Prioritize prompt/routing changes where low score and high traffic overlap.
5. Re-run tests and compare trace quality after each optimization release.
