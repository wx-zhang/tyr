# GAMR Domain Language

GAMR evaluates Tasks against Tyr through reusable configuration and individually traceable execution attempts.

## Task Structure

**Task**:
A versioned definition of the security objective, supporting plans, and Scenarios to evaluate.

**Scenario**:
An authored test definition within a Task, including its objective, steps, expected control, and evidence requirements.

**Scenario Execution**:
One runtime occurrence of a Scenario during an Experiment.

**Scenario ID**:
The stable identity of an authored Scenario definition.

**Scenario Execution ID**:
The unique identity of one Scenario occurrence in an Experiment.

## Experiment Lifecycle

**Experiment Preset**:
A saved, reusable configuration for evaluating a Task.

**Experiment**:
One execution attempt created from an Experiment Preset.

**Experiment State**:
The lifecycle state of an Experiment, from preparation through completion or interruption.

**Completion Outcome**:
The technical disposition of an Experiment or Scenario Execution, such as completed, blocked, failed, or cancelled.

**Objective Status**:
The assessment of whether a Scenario objective was achieved, not achieved, partial, not attempted, or unknown.

## Research and Approval

**Adversarial Researcher**:
The research role that proposes Task-specific Scenarios from prior evidence.

**Research Iteration**:
One cycle in which the Adversarial Researcher proposes and evaluates new Scenarios.

**Approval-gated**:
An action mode in which GAMR may request actions but Tyr requires an explicit human decision for every action.

## Operation Scope

**GAMR Experiment**:
An operation owned by GAMR for coordinating an Experiment.

**Tyr Operation**:
An individual request sent to Tyr for authorization or execution.

**Tyr Execution**:
The execution record produced by Tyr for an authorized operation.
