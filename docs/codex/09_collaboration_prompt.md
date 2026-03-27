# Collaboration Prompt

```text
Read AGENTS.md and docs/tasks.md.
Execute this stage only.

Now improve the multi-user collaboration/server architecture.

Goals:
- create a realistic starter collaboration backend
- support presence and near real-time updates
- keep client and server clearly separated

Tasks:
1. Improve the Python server implementation
2. Add or improve workbook session tracking
3. Add user presence tracking
4. Add support for showing:
   - who has a workbook open
   - which sheet another user is viewing
   - which cell or range another user is editing where practical
5. Add a simple real-time update mechanism using WebSockets or equivalent
6. Add a basic conflict-handling or locking strategy scaffold
7. Keep the design suitable for future enhancement

Requirements:
- do not fake full collaborative editing if not fully implemented
- provide a working starter architecture
- document limitations clearly
- update README collaboration sections

Output:
- updated server/collaboration files
- any new client integration files
- brief explanation of what is live now vs scaffolded
```
