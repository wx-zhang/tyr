---
name: commit-changes
description: Commit all intended changes with a clear, meaningful Git commit message.
---

# commit-changes

Commit all intended changes with a clear, meaningful Git commit message.

1. Review `git status` and `git diff`.
2. Stage only relevant changes.
3. Write a concise commit message that:

   * uses imperative mood;
   * describes **what changed and why**;
   * follows Conventional Commits when appropriate: `type(scope): summary`;
   * avoids vague messages like `update`, `fix`, or `changes`.
4. Commit the staged changes.
5. Verify the commit with `git status` and `git log -1 --oneline`.

Never commit secrets, generated junk, or unrelated changes.
