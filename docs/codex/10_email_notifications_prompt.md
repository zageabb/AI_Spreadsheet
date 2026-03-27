# Email Notifications Prompt

```text
Read AGENTS.md and docs/tasks.md.
Execute this stage only.

Now implement the email notification module for access control and account-related events.

Goals:
- send emails from the Python server for workbook sharing actions
- keep the email system modular and configurable

Tasks:
1. Implement an email service module
2. Add email templates for:
   - workbook invitation
   - access granted
   - access removed
   - optional password reset scaffold
3. Support SMTP or API-based providers via a configuration layer
4. Use env/config values instead of hardcoded credentials
5. Wire email sending into workbook sharing workflows
6. Add safe development-mode behaviour for testing

Requirements:
- keep secrets out of source code
- keep the module swappable for different email providers
- update README configuration and usage steps

Output:
- updated/new email-related files
- template files if used
- config examples
- short explanation of how email delivery is configured
```
