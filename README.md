# GameHive Agents

> An AI-powered multi-agent system for transforming game ideas into structured, playable game concepts through specialized autonomous AI agents.

## Overview

GameHive Agents is an Agentic AI project designed to assist with the early stages of game development.

Instead of relying on a single AI model to generate an entire game concept, GameHive uses multiple specialized AI agents that collaborate through a structured workflow.

Each agent is responsible for a specific part of the game design process, including story development, world building, gameplay mechanics, verification, routing, and self-correction.

The system also integrates Retrieval-Augmented Generation (RAG) to improve contextual accuracy and support more reliable outputs.

---

## What GameHive Does

A user starts by describing a game idea.

GameHive then processes the idea through multiple specialized AI agents to generate:

- Narrative foundations
- Characters
- Game worlds
- Gameplay mechanics
- Level concepts
- Structured game design outputs
- Cultural and factual verification
- Refined outputs through self-correction

---

## Multi-Agent Architecture

GameHive is built around specialized agents working together within an orchestrated workflow.

### Core Agents

- **Story Agent** — develops the narrative, conflict, and characters
- **World Engine** — creates the game world, settings, and progression
- **Gameplay Agent** — defines gameplay systems and core mechanics
- **Level Design Agent** — structures levels and player progression
- **Claim Extractor** — identifies factual and cultural claims
- **Claim Scope Router** — routes claims to the appropriate verification process
- **Culture Verifier** — evaluates culturally sensitive or contextual information
- **Game State Verifier** — checks consistency across generated game elements
- **Revision Gate** — determines whether generated content requires revision
- **Self-Correction Controller** — coordinates refinement and correction cycles

---

## Agentic Workflow

The system follows a structured AI workflow:


User Game Idea
      ↓
Story Generation
      ↓
World Building
      ↓
Gameplay Design
      ↓
Claim Extraction
      ↓
Routing & Verification
      ↓
Consistency Checking
      ↓
Self-Correction



## Project Screenshots

### Landing Page
![GameHive Landing Page](assets/landing-page.png)

### Game Idea Input
![Game Idea Input](assets/game-idea-input.png)

### Multi-Agent Workflow
![GameHive Multi-Agent Workflow](assets/agent-workflow.png)

### Narrative Generation
![Generated Narrative](assets/narrative-output.png)

### Generated Characters
![Generated Characters](assets/generated-characters.png)
