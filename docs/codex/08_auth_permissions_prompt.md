# Authentication and Permissions Prompt

```text
Read AGENTS.md and docs/tasks.md.
Execute this stage only.

Now strengthen authentication and workbook access control.

Goals:
- login must be via email address
- workbook owners must be able to control access
- roles must include owner, editor, viewer

Tasks:
1. Implement or improve user registration scaffold
2. Implement or improve login by email + password
3. Add password hashing
4. Add session or token handling appropriate to the architecture
5. Implement authorization checks for workbook access
6. Add workflows for:
   - create workbook
   - assign owner
   - invite user
   - grant editor access
   - grant viewer access
   - revoke access
7. Keep authorization separate from UI logic

Requirements:
- do not hardcode secrets
- structure auth so external identity providers could be added later
- keep access-control logic reusable across JSON and PostgreSQL-backed modes where practical
- update README usage notes

Output:
- updated auth and permissions files
- any new config/env examples
- brief explanation of login flow and sharing model
```
