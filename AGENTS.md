# Tyr Red Teaming Agent

The following repository contains a red teaming agent for Tyr.

## About Tyr

Tyr is a security and governance layer for AI agents. It sits between an AI agent and the tools, APIs, or company systems the agent can access, checking whether each action is authenticated, authorized, and compliant with defined policies before it is executed. In simple terms, Tyr acts like a firewall and access-control system for AI agents, helping prevent unsafe actions, prompt-injection abuse, unauthorized data access, and providing logs of what agents do.

## Core Standards & Syntax

- **Target Runtime**: Python 3.12+
- **Environment**: Use `uv` for dependency management.

## Coding standards

- The code must be self-explanatory. Make sure variable names are meaningful.
- Don't add comments unless it's necessary because of the unclear implementation or workarounds.
- Prefer simple solution that get the job done. Don't overengineer or suggest changes that maybe will be used in the future.
- Prefer lean files below 300 lines. If the file grows, move the new code to separate clear module.
- Always import on top of the file. Don't use dynamic imports unless needed.
