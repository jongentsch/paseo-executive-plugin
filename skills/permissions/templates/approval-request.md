# Permission decision needed

Host: [host ID and display name]
Worker: [title and full agent ID]
Request: [exact request ID]
Task: [goal and current state]
Action: [requested tool and exact command/input, with secret values redacted]
Working directory: [host-side directory, or state that it was not provided]
Scope and effects: [files, destinations, privileges, writes, execution, or other effects]
Why requested: [task connection and supporting evidence]
If denied: [known alternative or blocker; do not promise an unverified workaround]

Choose: allow this request, deny it, or deny and stop this worker.

After the decision, record the host/agent/request identity, matching input, the user's decision, tool response, and inspected worker state. Do not infer missing request details from a title alone.
