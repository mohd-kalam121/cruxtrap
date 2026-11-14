# CruxTrap — Interview Preparation Guide

## Project in One Line

> **CruxTrap** is an AI-driven SSH honeypot platform with a SOC-style dashboard that emulates a fake Ubuntu server, captures attacker credentials/commands, uses a Q-learning agent for adaptive responses, and streams enriched events through Redis into PostgreSQL for investigation and session replay.

---

## One-Minute Project Summary

- **What it does:** Exposes a fake SSH service that accepts all logins and observes what attackers do inside a simulated Linux environment.
- **How it works:** AsyncSSH accepts connections → fake filesystem + command emulation → Q-learning agent picks a response (Allow / Delay / Fake / Insult / Block) → events streamed via Redis Streams → enriched with GeoIP → stored in PostgreSQL → visualized in a FastAPI dashboard with session replay.
- **Why it matters:** Gives companies attacker behavior intelligence and deception capabilities without exposing production systems.

---

## Architecture (5 Services)

```
┌─────────────┐   events    ┌───────────┐  enriched   ┌────────────┐   queries   ┌──────────────┐
│ SSH Honeypot│ ──────────▶ │  Redis    │ ──────────▶ │  Pipeline  │ ──────────▶ │  PostgreSQL  │ ◀── FastAPI Dashboard
│ (AsyncSSH)  │   Streams   │ (EventBus)│             │  (GeoIP)   │             └─────────────┘
└─────────────┘             └───────────┘             └────────────┘
```

| Service | Responsibility |
|---|---|
| SSH Honeypot | Accepts connections, emulates Ubuntu shell, runs RL agent |
| Redis | Event bus using Redis Streams (decouples producer from DB) |
| Pipeline | Consumes events, adds GeoIP enrichment |
| PostgreSQL | Persistent storage for sessions, commands, credentials |
| FastAPI Dashboard | SOC-style UI, investigation, session replay |

All services run via **Docker Compose** (single-command startup).

---

## Q&A by Topic

### 1. Project Overview

**Q: Tell me about your project.**
A: CruxTrap is an AI-driven SSH honeypot platform with a SOC-style dashboard designed to observe attacker behavior rather than protect a production server. It exposes a fake SSH service that accepts login attempts, emulates a realistic Ubuntu environment, captures attacker commands and credentials, applies a Q-learning agent to decide how to respond, streams events through Redis, enriches them with GeoIP, stores them in PostgreSQL, and displays them through a FastAPI dashboard for investigation and session replay.

**Q: What technologies did you use?**
A: Python, AsyncSSH, AsyncIO, Redis Streams, PostgreSQL, FastAPI, Jinja2, Docker Compose, GeoIP, and Reinforcement Learning (Q-Learning).

**Q: Why did you build CruxTrap?**
A: I wanted a practical cybersecurity project demonstrating deception technology and attacker behavior analysis. Traditional tools block attacks; I wanted to study what attackers do *after* connecting. It also let me work with distributed services, async programming, RL, and SOC-style monitoring.

**Q: Why is this useful for companies?**
A: Honeypots help study attacker techniques, understand brute-force campaigns, collect threat intelligence, and improve detection — all without exposing production systems.

### 2. Problem & Motivation

**Q: What problem does CruxTrap solve?**
A: Organizations often know someone attempted an SSH login but lack visibility into what an attacker would do after gaining access. CruxTrap safely records credentials, commands, session timelines, and behavior in a controlled environment so analysts can study attacks without risking real assets.

**Q: Why not simply block attackers?**
A: Blocking prevents learning. A honeypot intentionally observes attackers to collect intelligence that improves future defenses.

**Q: Why did you choose SSH?**
A: SSH is one of the most attacked remote administration protocols. Attackers continuously brute-force SSH servers, making it ideal for studying login attempts, post-login behavior, and command execution.

**Q: Could this work with HTTP?**
A: Yes, but HTTP focuses on web attacks, while SSH gives an interactive shell where you can observe attacker commands and decision-making in real time.

### 3. Honeypot Concepts

**Q: What is a honeypot?**
A: A decoy system intentionally designed to attract attackers. Instead of serving legitimate users, it captures attacker behavior, tools, and techniques for analysis.

**Q: Does it protect production systems?**
A: Indirectly. It improves detection and threat intelligence but is not itself a firewall or intrusion prevention system.

**Q: What type of honeypot is CruxTrap?**
A: An SSH interaction honeypot that emulates a realistic Linux server, records attacker activity, and responds dynamically using a reinforcement learning agent.

**Q: Is it low-interaction or high-interaction?**
A: It sits between the two — realistic command interaction, but inside a controlled fake environment rather than a real OS.

**Q: Why accept every username and password?**
A: The goal is observation, not authentication. Accepting all credentials captures post-login behavior, which is more valuable than recording failed attempts.

**Q: Isn't that insecure?**
A: No. The attacker enters a fake environment with no access to a real OS or sensitive data.

**Q: What is deception technology?**
A: Deception technology intentionally misleads attackers by presenting fake systems, files, or services to waste their time and reveal their techniques.

**Q: How does CruxTrap implement deception?**
A: Via a realistic Ubuntu shell, fake files, fake credentials, and adaptive RL-based responses.

### 4. Session & Data Collection

**Q: What happens immediately after an attacker connects?**
A: The SSH server establishes the connection, accepts authentication, creates a unique session (UUID), initializes the fake filesystem, starts the command processor and RL agent, and begins capturing every interaction.

**Q: What uniquely identifies a session?**
A: A UUID generated when the session starts.

**Q: What information do you collect?**
A: Source IP, username, password, commands executed, session duration, RL decisions, GeoIP information, and session timeline.

**Q: Where is this stored?**
A: In PostgreSQL, after processing through the pipeline.

**Q: Why use a fake filesystem?**
A: It makes the environment believable while preventing attackers from interacting with a real OS — exposing the real filesystem would be a major security risk.

### 5. Reinforcement Learning

**Q: What is the role of the RL agent?**
A: It decides how the honeypot should respond to attacker commands based on previously learned experience.

**Q: What responses can it choose?**
A: Allow, Delay, Fake, Insult, Block.

**Q: Why Q-learning?**
A: Q-learning learns through interaction without labeled training data. Attacker behavior changes over time, so online learning suits this environment.

**Q: Why not supervised learning?**
A: Supervised learning needs labeled datasets, which are hard to obtain for evolving attacker behavior.

### 6. Architecture & Tech Choices

**Q: What makes CruxTrap different from a traditional honeypot?**
A: Unlike static honeypots, it has an adaptive RL agent, Redis event streaming, GeoIP enrichment, PostgreSQL persistence, and a SOC-style dashboard with session replay.

**Q: Which feature are you most proud of?**
A: Integrating reinforcement learning with an interactive SSH environment — it enables dynamic responses instead of fixed behavior.

**Q: How many services are running?**
A: Five: SSH Honeypot, Redis, Pipeline, PostgreSQL, and FastAPI Dashboard. Separated so each has a single responsibility — easier to maintain, scale, and debug.

**Q: Why Docker Compose?**
A: It defines all services, networking, dependencies, and volumes in one config — the whole environment starts consistently with a single command.

**Q: What is the purpose of Redis?**
A: Redis acts as the event bus between the SSH honeypot and the processing pipeline using Redis Streams, decoupling event generation from database writes so the honeypot never blocks if PostgreSQL is temporarily unavailable.

**Q: Why PostgreSQL?**
A: Reliable relational storage, strong indexing, ACID transactions, efficient querying. The data has clear relationships (attackers → sessions → actions), so relational fits better than MongoDB.

**Q: Why FastAPI?**
A: Asynchronous, high-performance, integrates naturally with AsyncIO and async PostgreSQL drivers. Flask lacks native async support, automatic validation, and comparable performance.

### 7. Future Roadmap

**Q: If you had two more months, what would you add?**
A: Real threat intelligence integrations, alerting, campaign correlation, dashboard authentication, multiple honeypot types, SIEM integration, and cloud deployment — keeping the existing architecture intact.

**Q: Which would you implement first?**
A: Dashboard authentication — protecting analyst access is a prerequisite for adding operational features.

---

## Quick Fact Sheet (Memory Cards)

| Concept | One-liner |
|---|---|
| Honeypot | Decoy system to attract and study attackers |
| CruxTrap type | SSH interaction honeypot (between low/high interaction) |
| Credential policy | Accepts all — observation > authentication |
| RL responses | Allow, Delay, Fake, Insult, Block |
| RL algorithm | Q-learning (online, no labeled data needed) |
| Event bus | Redis Streams |
| Storage | PostgreSQL |
| Dashboard | FastAPI + Jinja2, SOC-style, session replay |
| Enrichment | GeoIP (in pipeline) |
| Deploy | Docker Compose, 5 services |
| Session ID | UUID at connection |

---

## Batch 2 — Architecture (Questions 21–40) ⭐⭐⭐⭐☆

> **Why interviewers care:** This section decides whether you actually built the project. Expect deep follow-ups on event flow, failure scenarios, and coupling.

### System Design & Event Flow

**Q21: Explain your complete architecture.**
A: CruxTrap follows a distributed microservice-style architecture with five services:

```
Attacker
   │
   ▼
SSH Honeypot (AsyncSSH)
   │
   ▼
Redis Streams
   │
   ▼
Pipeline Service
   │
   ▼
PostgreSQL
   │
   ▼
FastAPI Dashboard
```

The SSH honeypot accepts attacker connections and generates events. Those events are written into Redis Streams. The pipeline service consumes those events, enriches them with GeoIP information, and stores them in PostgreSQL. Finally, the FastAPI dashboard queries PostgreSQL and presents the data through a SOC-style interface.

**Follow-up: Why did you separate the pipeline instead of writing directly to PostgreSQL?**
A: The separation decouples event generation from storage. The honeypot only needs Redis. If PostgreSQL becomes slow or temporarily unavailable, the honeypot can continue capturing events without blocking.

**Q22: Walk me through an attacker connecting.**
A: The attacker connects to SSH → AsyncSSH accepts the connection → authentication succeeds → SessionRunner creates a new session → fake filesystem is initialized → command processor starts → RL agent becomes active → connection event is written to Redis → commands are executed → every command becomes an event → pipeline consumes events → GeoIP enrichment happens → data is stored in PostgreSQL → dashboard displays the session.

**Follow-up: Which component creates the session ID?**
A: SessionRunner generates a UUID when the session starts.

**Q23: Why use multiple services instead of one application?**
A: Each service has a single responsibility — SSH captures attacks, pipeline processes events, database stores data, API serves the dashboard. This makes the project easier to debug, maintain, and scale independently.

**Follow-up: Could everything run inside one Python application?**
A: Yes. But separating responsibilities improves modularity and allows independent scaling.

**Q24: Which service communicates first?**
A: The SSH Honeypot. It is the only externally exposed service that interacts with attackers; every other service depends on the events it generates.

**Follow-up: Which service communicates with the attacker directly?**
A: Only the AsyncSSH Honeypot.

**Q25: Why is Redis placed between the Honeypot and PostgreSQL?**
A: Redis acts as an event buffer. Instead of blocking while writing to PostgreSQL, the honeypot pushes events into Redis and the pipeline processes them asynchronously.

**Follow-up: What happens if PostgreSQL is temporarily unavailable?**
A: The pipeline cannot persist events until the database is reachable again — but the decoupled design means the honeypot itself is not waiting on database writes.

**Q26: What is the responsibility of the Pipeline?**
A: Reading events from Redis Streams, GeoIP enrichment, creating or updating attacker records, creating or updating sessions, recording every command, and persisting everything into PostgreSQL.

**Follow-up: Does the Pipeline communicate with the attacker?**
A: No. It only processes internal events.

**Q27: Why doesn't the dashboard connect to Redis?**
A: Redis is for event transport; PostgreSQL is the system of record. The dashboard queries PostgreSQL because it stores structured attacker, session, and action data.

**Follow-up: Why is PostgreSQL better for dashboards?**
A: Relational queries, filtering, joins, ordering, and aggregation are much easier and more efficient than querying transient event streams.

**Q28: Why is PostgreSQL after the Pipeline?**
A: Events should be enriched and normalized before permanent storage; otherwise the database would contain incomplete or inconsistent data.

**Follow-up: What enrichment is currently implemented?**
A: GeoIP enrichment that adds country and city information.

**Q29: Why is FastAPI separated from PostgreSQL?**
A: The dashboard should never expose database access directly. FastAPI acts as the application layer — it queries PostgreSQL and renders HTML pages.

**Follow-up: Could the browser access PostgreSQL directly?**
A: No. That would be insecure and bypass application logic.

### Data & Responsibility Boundaries

**Q30: What data flows through Redis?**
A: Connection events → login events → command events → session close events. Every event represents something the attacker did.

**Follow-up: Does Redis store images or files?**
A: No. It stores structured event messages.

**Q31: Which service owns business logic?**
A: The SSH Honeypot — it contains the RL Agent, Command Processor, Fake Filesystem, and Session management.

**Follow-up: Does FastAPI contain business logic?**
A: No. FastAPI primarily reads data from PostgreSQL and renders dashboard pages.

**Q32: Why isn't the RL agent inside the Pipeline?**
A: The RL agent must make decisions *before* the attacker receives a response. If it ran inside the Pipeline, the command would already have been executed.

**Follow-up: Why is latency important?**
A: The attacker expects immediate command responses. Decision-making must happen inside the honeypot before output is returned.

**Q33: Why is GeoIP inside the Pipeline?**
A: GeoIP is enrichment — it doesn't affect attacker interaction. Keeping it in the Pipeline prevents unnecessary work in the honeypot and keeps responsibilities separate.

**Follow-up: Could GeoIP run inside the Honeypot?**
A: Technically yes, but separating enrichment keeps the honeypot focused on handling attacker interactions.

**Q34: Why store commands?**
A: Commands reveal attacker intent — reconnaissance, privilege escalation, persistence, payload download. Studying commands is more valuable than only knowing that someone logged in.

**Follow-up: Why not store only login attempts?**
A: Login attempts don't show what attackers try to accomplish after access is gained.

**Q35: What does the dashboard display?**
A: Attacker information, sessions, commands, GeoIP information, RL decisions, and session replay.

**Follow-up: Where does the dashboard obtain this information?**
A: From PostgreSQL.

### Scaling & Failure Scenarios

**Q36: Which service is easiest to scale?**
A: The FastAPI dashboard — it is stateless, so multiple instances can serve requests using the same PostgreSQL database.

**Follow-up: Which service is hardest to scale?**
A: The SSH honeypot, because it maintains live attacker sessions and contains the RL decision logic.

**Q37: If Redis crashes, what happens?**
A: The honeypot cannot successfully publish new events to Redis until connectivity is restored, so downstream processing is interrupted. The event pipeline depends on Redis for transport.

**Follow-up: Does PostgreSQL receive new events?**
A: No. Without Redis, the Pipeline has no new events to consume.

**Q38: If PostgreSQL crashes, what happens?**
A: The Pipeline cannot persist processed events, and the dashboard cannot retrieve stored session information until PostgreSQL is available again.

**Follow-up: Does the SSH service stop accepting connections?**
A: No. It is independent of PostgreSQL because it communicates through Redis rather than directly with the database.

**Q39: Why is this architecture considered loosely coupled?**
A: Each service communicates through clearly defined interfaces — the SSH service doesn't know database internals, the dashboard doesn't know how the honeypot works, and each component focuses on its own responsibility.

**Follow-up: What is tight coupling?**
A: Tight coupling means one service directly depends on another service's internal implementation, making changes more difficult.

**Q40: Explain the architecture in one sentence.**
A: CruxTrap captures attacker activity through an AsyncSSH honeypot, transports events using Redis Streams, enriches and stores them via a Pipeline and PostgreSQL, and presents them through a FastAPI-based SOC dashboard.

**Follow-up: If you had to remove one service, which would be hardest to remove?**
A: The SSH Honeypot. It is the entry point of the entire system and generates all attacker events — without it, the rest of the architecture has no data to process.

---

## Batch 3 — SSH Honeypot + AsyncSSH Deep Dive (Questions 41–60) ⭐⭐⭐⭐☆

> **Why interviewers care:** Tests whether you understand the internals of your own code — session lifecycle, async I/O, emulation choices.

### Honeypot Structure

**Q41: Explain the SSH Honeypot architecture.**
A: The SSH honeypot is the entry point of CruxTrap. It uses AsyncSSH to emulate a realistic Ubuntu SSH server. It accepts incoming connections, authenticates users, creates isolated sessions, initializes a fake filesystem, executes commands through a command processor, consults the Q-learning agent to decide responses, and publishes all attacker activity to Redis Streams.

```
Attacker
   │
   ▼
AsyncSSH Server
   │
   ▼
Authentication
   │
   ▼
SessionRunner
   │
   ├────────► Fake File System
   │
   ├────────► Command Processor
   │
   ├────────► RL Agent
   │
   ▼
RedisEmitter
   │
   ▼
Redis Streams
```

**Follow-up: Is the SSH Honeypot stateful?**
A: Yes. Each attacker gets an independent session containing its own fake filesystem, session ID, command history, and RL context.

**Q42: Why did you use AsyncSSH?**
A: AsyncSSH is a Python library for implementing SSH servers and clients using asyncio. It provides the SSH protocol implementation, authentication support, PTY handling, interactive shells, and async execution — so I could build a fully asynchronous SSH server without implementing the SSH protocol from scratch.

**Follow-up: Why not Paramiko?**
A: Paramiko is primarily designed for SSH clients. AsyncSSH provides much better support for asynchronous SSH servers and scales naturally with asyncio.

**Q43: What happens when an attacker connects?**
A: The sequence is: TCP connection arrives → AsyncSSH accepts → `connection_made()` records client IP and port → authentication begins → any username/password is accepted → AsyncSSH starts a new process → SessionRunner creates a session → fake filesystem is initialized → RL agent starts → Ubuntu banner is displayed → command loop begins.

**Follow-up: Which method first receives the connection?**
A: `connection_made()`. It stores information such as the client's IP address and port.

**Q44: Why accept every password?**
A: The objective is to observe post-authentication attacker behavior. If authentication failed, we would never learn reconnaissance commands, payload downloads, privilege escalation attempts, or persistence techniques.

**Follow-up: Is this dangerous?**
A: No. The attacker enters a fake environment; no real operating system is exposed.

### SessionRunner & Session Management

**Q45: What is SessionRunner?**
A: SessionRunner manages one SSH session — creating session IDs, creating fake filesystems, initializing the command processor, communicating with the RL agent, sending prompts, reading commands, and emitting events.

**Follow-up: Is one SessionRunner shared?**
A: No. Every attacker receives a separate SessionRunner instance.

**Q46: Why generate a UUID?**
A: Every SSH connection must be uniquely identifiable. The UUID links together commands, login events, disconnect events, replay, and database records.

**Follow-up: Could you use the IP instead?**
A: No. One IP can create multiple independent SSH sessions.

**Q47: What happens after authentication?**
A: SessionRunner starts → fake filesystem is built → command processor is initialized → RL session starts → Redis connection events are emitted → Ubuntu banner is displayed → prompt loop begins.

**Follow-up: Does the attacker notice anything unusual?**
A: No. The goal is to make the environment appear like a normal Ubuntu server.

### Fake Filesystem & Commands

**Q48: Why create a fake filesystem?**
A: Attackers expect Linux directories such as `/etc`, `/home`, `/root`, `/var`, `/usr`, `/proc`. Without these, the honeypot would immediately look fake.

**Follow-up: Are these real directories?**
A: No. Everything exists only in memory.

**Q49: How are commands processed?**
A: Every command follows this flow: Attacker Command → Read Input → Classification → RL Decision → Command Processor → Generate Output → Redis Event → Display Output.

**Follow-up: Who executes commands?**
A: The CommandProcessor.

**Q50: Does the honeypot execute Linux commands?**
A: No. It simulates them — `ls`, `pwd`, `cat`, `whoami`, `ps`, `find`, `grep` — each returning realistic fake output.

**Follow-up: Why not execute real commands?**
A: Executing real commands would allow attackers to interact with the host system, which is unsafe.

**Q51: What is PTY?**
A: PTY stands for Pseudo Terminal. It lets the attacker interact with the SSH session as if connected to a real terminal.

**Follow-up: Why is PTY important?**
A: Without a PTY, interactive shell behavior — prompts, command editing, terminal echo — would not feel realistic.

**Q52: How does the server read commands?**
A: For PTY sessions, commands are read one character at a time. This enables echo, backspace, Ctrl+C, Ctrl+D, and realistic typing.

**Follow-up: Why not use `readline()`?**
A: Character-by-character reading provides much finer control over terminal behavior.

**Q53: Why emulate Ubuntu?**
A: Ubuntu is one of the most common Linux distributions in servers — attackers expect Ubuntu-style directories, commands, banners, and configuration files.

**Follow-up: Could you emulate CentOS?**
A: Yes. Only the filesystem, banners, and command outputs would need to change.

**Q54: What happens if the attacker types an unknown command?**
A: The CommandProcessor returns a realistic Linux error: `command not found`.

**Follow-up: Does it crash?**
A: No. The session continues normally.

**Q55: How is realism maintained?**
A: Through the Ubuntu banner, realistic prompt, fake filesystem, fake SSH keys, fake `/etc/passwd`, fake logs, fake `.bash_history`, and realistic command outputs.

**Follow-up: Why is realism important?**
A: If attackers realize they are inside a honeypot, they change their behavior.

### Credentials & Isolation

**Q56: How are login credentials stored?**
A: The honeypot captures username, password, session ID, and IP address, and sends them as structured events through Redis for later persistence.

**Follow-up: Are passwords hashed?**
A: No. The project intentionally stores captured credentials as plaintext because collecting attacker-supplied credentials is part of the honeypot's purpose.

**Q57: Does each attacker receive the same filesystem?**
A: No. Each session builds its own fake filesystem instance, keeping sessions isolated from one another.

**Follow-up: Can attackers modify another attacker's files?**
A: No. Each session has its own isolated in-memory environment.

### AsyncIO, Lifecycle & Learning

**Q58: Why use AsyncIO?**
A: AsyncIO allows the server to handle many SSH sessions concurrently without creating one OS thread per connection.

**Follow-up: What is the benefit?**
A: Better scalability with lower memory overhead compared to a thread-per-connection model.

**Q59: How is session termination handled?**
A: When the attacker exits or the session is terminated: session statistics are finalized, closing events are emitted, the RL agent records the terminal reward, and the session state is saved.

**Follow-up: Does the RL agent learn at session end?**
A: Yes. The final reward is incorporated before the session finishes, allowing the Q-table to be updated.

**Q60: Explain the complete SSH lifecycle.**
A:

```
TCP Connection → AsyncSSH accepts → Authentication → SessionRunner
→ UUID generated → Fake File System → RL Agent → Command Processor
→ Interactive Shell → Redis Events → Disconnect → RL Update → Session Closed
```

**Follow-up: Which component is the heart of the SSH service?**
A: SessionRunner. It coordinates the fake filesystem, command processor, RL agent, session lifecycle, and event emission, making it the central component of each attacker session.

---

## Batch 4 — Reinforcement Learning (Q-Learning) Deep Dive (Questions 61–80) ⭐⭐⭐⭐⭐

> **Why interviewers care:** The hardest section. Expect follow-ups on the Q-learning equation, hyperparameters, and why RL at all. Master this — it's often the differentiator.

### Fundamentals & Why RL

**Q61: Why did you use Reinforcement Learning in CruxTrap?**
A: I wanted the honeypot to adapt its responses instead of always behaving the same way. Traditional honeypots return fixed responses. Here, a Q-learning agent learns from attacker interactions and selects actions — allow a command, delay the response, return fake information, insult the attacker, or block the session. This makes the interaction more dynamic and better suited to studying attacker behavior.

**Follow-up: Why not hard-code rules?**
A: Hard-coded rules always produce the same response for the same input. Q-learning lets the policy improve over time based on interaction outcomes rather than relying only on predefined logic.

**Q62: What is Reinforcement Learning?**
A: A machine learning paradigm where an agent learns by interacting with an environment: observe state → choose action → receive reward → update policy to maximize long-term cumulative reward.

**Follow-up: What is the environment in your project?**
A: The attacker session inside the SSH honeypot.

**Q63: What is the agent?**
A: The Q-learning agent is the decision-making component. It receives the command classification and session phase, and chooses the best response.

**Follow-up: Does the agent execute commands?**
A: No. The CommandProcessor executes commands; the RL agent only decides how the honeypot should respond.

### State, Phases & Actions

**Q64: What is the state?**
A: A combination of **Pattern + Session Phase**, represented as `pattern|phase` — e.g., `credential_access|early`, `download|mid`, `none|late`.

**Follow-up: Why combine them?**
A: The same command can deserve a different response depending on whether it occurs early, midway, or late in the attacker's session.

**Q65: What are the phases?**
A: Three phases — **Early** (first few commands), **Mid** (middle of session), **Late** (long-running interaction) — letting the agent consider attacker progression, not just individual commands.

**Follow-up: Why not use elapsed time?**
A: The implementation uses command count to determine the phase — simple, deterministic, and avoids dependence on variable network delays.

**Q66: What is the action space?**
A: Five actions: **ALLOW, DELAY, FAKE, INSULT, BLOCK**. Each changes how the honeypot responds.

**Follow-up: What does FAKE do?**
A: Instead of returning real system data, the honeypot returns realistic fake information.

**Q67: Explain each action.**
A:
- **ALLOW** — return the normal simulated command output.
- **DELAY** — pause before responding, imitating network latency or a busy system.
- **FAKE** — return believable fake files, credentials, or command results.
- **INSULT** — return a humorous or taunting response instead of the expected output.
- **BLOCK** — terminate or block the interaction to end the session.

**Follow-up: Which action is most common initially?**
A: Benign commands are typically warm-started toward ALLOW until the agent has learned otherwise.

### Exploration vs Exploitation

**Q68: How does the agent choose an action?**
A: It classifies the command, determines the session phase, constructs the state (`pattern|phase`), then uses an **ε-greedy policy** — sometimes exploring, otherwise exploiting the highest-valued action.

**Follow-up: What is exploitation?**
A: Selecting the action with the highest learned Q-value for the current state.

**Q69: What is ε-greedy?**
A: A policy that balances exploration and exploitation: with probability ε choose a random action; otherwise choose the best-known action.

**Follow-up: Why is exploration necessary?**
A: Without it, the agent might never discover actions that produce better long-term rewards.

**Q70: What is epsilon?**
A: The exploration parameter — high ε means more random actions, low ε means more learned behavior.

**Follow-up: Does epsilon remain constant?**
A: No. It decays over time until reaching a configured minimum.

**Q71: Why decay epsilon?**
A: Initially the agent needs exploration; once enough experience is gathered, it should rely more on learned knowledge.

**Follow-up: What happens if epsilon never decreases?**
A: The agent would keep making many random decisions and might never converge toward a stable policy.

### Q-Table, Rewards & the Learning Update

**Q72: What is the Q-table?**
A: A table storing the expected value of taking a particular action in a particular state.

```
State              Action   Q-value
download|early     FAKE     2.3
download|early     BLOCK    1.4
credential|late    DELAY    0.9
```

**Follow-up: Is this a neural network?**
A: No. The implementation uses a dictionary-backed Q-table, not a neural network.

**Q73: What is a reward?**
A: A measure of how desirable an action's outcome is — positive rewards encourage similar behavior, negative rewards discourage it.

**Follow-up: Who assigns the reward?**
A: The RL implementation computes it internally based on attacker engagement and session progression.

**Q74: How is reward calculated?**
A: It rewards continued attacker engagement — higher reward while the attacker keeps interacting, lower if the session ends quickly. The goal is keeping attackers interacting while safely observing them.

**Follow-up: Why reward engagement?**
A: Longer interactions produce more telemetry, commands, and behavioral information for analysis.

**Q75: What is Temporal Difference (TD) learning?**
A: TD learning updates the Q-value by combining the current estimate with the observed reward and an estimate of future rewards — the agent learns incrementally after each interaction.

**Follow-up: Does your implementation use TD learning?**
A: Yes. The Q-learning update uses a temporal-difference update internally.

**Q76: Explain the Q-learning equation.**
A:

```
Q(s,a) = Q(s,a) + α × [r + γ × maxQ(s',a') − Q(s,a)]
```

Where `Q(s,a)` = current value, `α` = learning rate, `r` = immediate reward, `γ` = discount factor, `maxQ(s',a')` = best future estimate.

**Follow-up: What does α control?**
A: The learning rate — how much new experience influences the existing Q-value.

**Q77: What is the discount factor γ?**
A: It controls how much future rewards matter — large γ makes future rewards important, small γ makes immediate rewards dominate.

**Follow-up: Why use gamma?**
A: Actions may have consequences beyond the current command, so the agent should consider future outcomes when learning.

### Limitations & Lifecycle

**Q78: Why not Deep Q Networks (DQN)?**
A: The state space is small and discrete. Tabular Q-learning is simpler, easier to explain, requires no GPU, and is sufficient for the implemented state-action space.

**Follow-up: When would DQN become useful?**
A: If the state space became much larger or continuous — e.g., richer behavioral features or embeddings — a neural network approximation would be more appropriate.

**Q79: What happens when the session ends?**
A: The final reward is computed, the terminal Q-value is updated, and the learned state is persisted — so future sessions benefit from previous experience.

**Follow-up: Why save the learned state?**
A: Without persistence, the agent would start learning from scratch every time the service restarted.

**Q80: Explain the complete RL workflow.**
A:

```
Attacker Command → Pattern Classification → Determine Session Phase
→ Create State → ε-Greedy Policy → Choose Action
→ Command Processor Executes Response → Attacker Reacts
→ Reward Calculated → TD Update → Q-table Updated → State Saved
```

**Follow-up: Which component actually modifies the Q-table?**
A: The Q-learning agent updates its own Q-table using the TD update rule after observing rewards from attacker interactions — it maintains and persists the learned policy.

---

### Batch 4 Key Concepts Checklist

- ✅ Why RL was chosen — adaptive vs fixed responses
- ✅ Agent / Environment / State (`pattern|phase`) / Action space (5 actions)
- ✅ Reward function — rewards engagement
- ✅ ε-greedy exploration + epsilon decay
- ✅ Q-table (dictionary-backed, not a neural network)
- ✅ TD learning + full Q-learning equation (`α`, `r`, `γ`, `maxQ(s',a')`)
- ✅ Warm-start (benign → ALLOW)
- ✅ State persistence at session end

---

## Batch 5 — Redis & Event-Driven Architecture (Questions 81–100) ⭐⭐⭐⭐☆

> **Why interviewers care:** Tests event-driven thinking — Redis commands, failure scenarios, and why decoupling matters. Expect "what if Redis goes down" style questions.

### Why Redis & Streams

**Q81: Why did you use Redis in CruxTrap?**
A: Redis acts as the event bus between the SSH honeypot and the pipeline service. Instead of writing directly to PostgreSQL, the honeypot publishes events to Redis Streams. The pipeline independently consumes, enriches, and stores them — decoupling event generation from event processing.

**Follow-up: Why not connect directly to PostgreSQL?**
A: If the honeypot wrote directly to PostgreSQL, every attacker command would wait for a database operation to complete. Redis lets the honeypot publish events quickly while persistence happens asynchronously.

**Q82: Why Redis Streams instead of Redis Pub/Sub?**
A: Pub/Sub delivers messages only to currently connected subscribers — messages are lost if a subscriber is offline. Redis Streams persist events, supporting later processing, acknowledgements, replay, and consumer groups.

**Follow-up: Why is persistence important?**
A: If the pipeline restarts, it can continue consuming stored events instead of losing attacker telemetry.

**Q83: What is a Redis Stream?**
A: An append-only data structure designed for ordered event storage. Each event receives a unique stream ID and remains available until trimmed or deleted.

**Follow-up: Does Redis assign IDs?**
A: Yes. Redis automatically assigns a unique stream ID to every event added using XADD.

**Q84: What events are stored in Redis?**
A: SSH connection, login success, command execution, and session close — each containing structured info such as IP, timestamp, session ID, and event-specific data.

**Follow-up: Are screenshots or binaries stored?**
A: No. Only structured event data.

### Publishing & Consuming

**Q85: How does the honeypot publish events?**
A: The SSH service uses a **RedisEmitter** component. Whenever an important event occurs, it serializes the event and publishes it into the `honeypot:events` stream.

**Follow-up: Does the pipeline know about the SSH service?**
A: No. It only knows about Redis Streams — this loose coupling lets each service evolve independently.

**Q86: What is XADD?**
A: The Redis Streams command that appends a new event to a stream. Every attacker event generated by the honeypot is added using this operation.

**Follow-up: Does XADD overwrite previous events?**
A: No. It appends while preserving the order of existing events.

**Q87: What is a Consumer Group?**
A: A mechanism allowing multiple consumers to read from the same stream without processing the same message twice — Redis tracks which consumer received which messages.

**Follow-up: Why use Consumer Groups?**
A: They enable workload distribution and coordinated processing across multiple pipeline instances.

**Q88: How does your pipeline read events?**
A: Using **XREADGROUP** to consume from the `honeypot:events` stream — it blocks while waiting for new messages, then processes them in batches.

**Follow-up: Why not poll continuously?**
A: Blocking reads are more efficient — they avoid constant CPU usage when no events are available.

**Q89: What happens after an event is read?**
A: The pipeline parses the event → performs GeoIP enrichment → updates attacker information → updates session information → inserts session actions → writes enriched data → acknowledges the processed message.

**Follow-up: Is GeoIP performed before or after storage?**
A: Before. The event is enriched first, then persisted with the additional location information.

### Acknowledgements & Recovery

**Q90: What is XACK?**
A: It tells Redis that a message has been successfully processed. Once acknowledged, the message no longer needs to remain pending for that consumer group.

**Follow-up: What if you never acknowledge a message?**
A: It remains in the Pending Entries List (PEL) and may need recovery or reassignment, depending on the consumer group's handling.

**Q91: What is the Pending Entries List (PEL)?**
A: A list of messages delivered to consumers but not yet acknowledged — it helps Redis track unfinished work.

**Follow-up: Why is the PEL useful?**
A: If a consumer crashes after receiving a message but before acknowledging it, the message can be recovered instead of disappearing.

**Q92: How does your pipeline enrich events?**
A: It performs GeoIP lookups based on the attacker's source IP; the resulting country and city information is added before writing to PostgreSQL.

**Follow-up: Does the pipeline call external threat intelligence APIs?**
A: No. The implemented version performs GeoIP enrichment only — other threat-intelligence integrations are not part of the implemented project.

**Q93: Why separate enrichment from the honeypot?**
A: The honeypot must respond to attackers as quickly as possible — enrichment in the pipeline prevents extra processing from increasing response latency.

**Follow-up: Could enrichment run inside the honeypot?**
A: Technically yes, but separating responsibilities improves performance and modularity.

### Failure Scenarios & Scaling

**Q94: What happens if Redis goes down?**
A: The SSH service cannot successfully publish new events, and the pipeline cannot consume new messages until Redis becomes available again.

**Follow-up: Does the SSH service still accept connections?**
A: Yes. However, new event publication will fail until Redis connectivity is restored.

**Q95: What happens if the pipeline crashes?**
A: The SSH honeypot continues publishing events to Redis. When the pipeline restarts, it resumes consuming from the stream.

**Follow-up: Why doesn't the honeypot stop?**
A: Because event generation and event processing are independent services connected only through Redis.

**Q96: Why is Redis faster than PostgreSQL for messaging?**
A: Redis stores data in memory and is optimized for very low-latency operations — ideal for event transport, while PostgreSQL is optimized for durable relational storage and querying.

**Follow-up: Does Redis replace PostgreSQL?**
A: No. They serve different purposes: Redis transports events; PostgreSQL stores long-term structured data.

**Q97: Can multiple pipeline instances consume the same stream?**
A: Yes — Consumer Groups allow multiple consumers to share the workload while coordinating message ownership.

**Follow-up: Will every consumer process every message?**
A: No. Within a consumer group, each message is delivered to one consumer unless recovery or reassignment occurs.

**Q98: Why use asynchronous processing?**
A: The honeypot must stay responsive to attackers — publishing an event is much faster than waiting for enrichment and database writes synchronously.

**Follow-up: What benefit does this provide?**
A: Lower response latency for attacker interactions and better separation of responsibilities.

**Q99: Explain the complete event pipeline.**
A:

```
Attacker Command → RedisEmitter → XADD → honeypot:events
→ XREADGROUP → Pipeline → GeoIP Enrichment → PostgreSQL → Dashboard
```

**Follow-up: Where does GeoIP fit in this flow?**
A: Immediately after the pipeline consumes the event and before it is stored in PostgreSQL.

**Q100: Why is Redis important in your architecture?**
A: Redis is the communication backbone of CruxTrap — it decouples the honeypot from the pipeline, supports asynchronous event processing, provides durable stream semantics with acknowledgements and consumer groups, and keeps the system modular and scalable.

**Follow-up: If Redis were removed, what would you replace it with?**
A: For a small project, direct database writes could work but would reduce decoupling and increase latency. For larger deployments, a distributed event streaming platform such as Kafka would be a stronger alternative due to its scalability and long-term event retention.

---

### Batch 5 Key Concepts Checklist

- ✅ Why Redis was chosen — event bus, decoupling
- ✅ Redis Streams vs Pub/Sub (persistence wins)
- ✅ XADD / XREADGROUP / Consumer Groups / XACK / PEL
- ✅ Asynchronous event processing (latency)
- ✅ GeoIP enrichment flow (before storage)
- ✅ Failure scenarios: Redis down, pipeline crash
- ✅ Scalability: multiple consumers, Kafka as upgrade path

---

## Batch 6 — PostgreSQL & Database Design (Questions 101–120) ⭐⭐⭐⭐☆

> **Why interviewers care:** Tests schema thinking — relationships, normalization, indexes, ACID, and whether you understand why relational fits this project.

### Why PostgreSQL & Schema

**Q101: Why did you choose PostgreSQL?**
A: The project stores structured, relational data with clear relationships between attackers, sessions, and session actions. PostgreSQL provides ACID compliance, indexing, foreign keys, strong query capabilities, and excellent support for analytical queries.

**Follow-up: Why not MongoDB?**
A: MongoDB is useful for flexible document storage, but CruxTrap has well-defined relationships — one attacker → multiple sessions → multiple commands per session — naturally modeled in a relational database.

**Q102: How many tables are in your database?**
A: Three — `attackers`, `sessions`, `session_actions` — each representing a different level of abstraction.

**Follow-up: Why not store everything in one table?**
A: A single table would duplicate attacker information for every command, waste storage, and make queries harder. Normalization avoids redundancy.

**Q103: Explain the attackers table.**
A: Stores information belonging to an attacker rather than an individual session: source IP, username, country, city, total connections, total commands, first seen, last seen.

**Follow-up: Why doesn't it store commands?**
A: Commands belong to individual sessions, not the attacker profile.

**Q104: Explain the sessions table.**
A: One row per SSH connection: session ID, source IP, username, start time, end time, duration, command count, login success.

**Follow-up: Can one attacker have multiple sessions?**
A: Yes. One attacker can connect multiple times.

**Q105: Explain the session_actions table.**
A: Stores every action during a session — login, commands, disconnect. Each row records: session ID, action sequence, command, username, password, RL action, RL pattern, timestamp.

**Follow-up: Why separate actions from sessions?**
A: A session contains many events; a separate table supports the one-to-many relationship and simplifies querying.

### Relationships & Integrity

**Q106: What is the relationship between the tables?**
A:

```
Attacker (1) ──▶ Many Sessions ──▶ Many Session Actions
```

**Follow-up: What type of relationship is this?**
A: One-to-many.

**Q107: Why use foreign keys?**
A: They maintain referential integrity — e.g., every session action must belong to a valid session.

**Follow-up: What happens if a session is deleted?**
A: Related session actions are removed automatically through the configured cascading delete behavior.

**Q108: What is normalization?**
A: Organizing data to reduce redundancy and improve consistency — attacker info is stored once and referenced, not repeated in every command row.

**Follow-up: Which normal form is your schema closest to?**
A: The implemented schema follows the principles of Third Normal Form (3NF) — related entities are separated into tables with relationships.

**Q109: Why store session IDs?**
A: The session ID uniquely identifies every SSH connection and links login events, commands, disconnect events, replay, and database records.

**Follow-up: Could IP address replace session ID?**
A: No. One IP can create many independent sessions.

### Indexes, ACID & UPSERT

**Q110: What indexes do you use?**
A: Indexes on frequently queried columns — attacker last seen, session source IP, session creation time, session actions by session ID — improving lookup and dashboard performance.

**Follow-up: Why create indexes?**
A: Indexes reduce the amount of data the database must scan when executing queries.

**Q111: What is ACID?**
A: Atomicity, Consistency, Isolation, Durability — properties that ensure reliable transaction processing.

**Follow-up: Which property is most important here?**
A: Durability — once attacker data is stored, it should survive crashes and restarts.

**Q112: What is an UPSERT?**
A: Insert a new row if it does not exist, or update the existing row if it already exists.

**Follow-up: Why use UPSERT?**
A: It prevents duplicate attacker and session records while allowing existing records to be updated.

**Q113: Why use ON CONFLICT?**
A: It implements UPSERT behavior in PostgreSQL — if a unique key already exists, PostgreSQL updates the existing row instead of erroring.

**Follow-up: Which tables use ON CONFLICT?**
A: The pipeline uses it for attacker and session updates to keep records current without creating duplicates.

### Querying, Failure & Performance

**Q114: How does the dashboard get data?**
A: The FastAPI service executes SQL queries against PostgreSQL and renders results into HTML pages — the browser never accesses PostgreSQL directly.

**Follow-up: Why not allow direct browser access?**
A: Direct database access would be insecure and bypass application logic.

**Q115: Why store timestamps?**
A: They let analysts replay sessions, compute durations, identify attack timelines, and sort recent activity.

**Follow-up: Which timestamps are important?**
A: Start time, end time, action timestamp, first seen, and last seen.

**Q116: What SQL queries does your dashboard perform?**
A: Counting attackers, counting sessions, retrieving recent sessions, listing attacker profiles, and loading session actions for replay.

**Follow-up: Why use SQL instead of reading Redis?**
A: Redis transports events; PostgreSQL stores structured historical data optimized for querying.

**Q117: What happens if PostgreSQL crashes?**
A: The pipeline cannot persist new events and the dashboard cannot retrieve historical data until it's restored — the honeypot stays independent because it communicates through Redis.

**Follow-up: Will attacker sessions immediately disconnect?**
A: No. The SSH service does not depend directly on PostgreSQL for handling interactive sessions.

**Q118: How would you improve database performance?**
A: Additional indexes for high-volume queries, partitioning very large tables, archiving old session data, read replicas for dashboard traffic, and optimizing expensive queries.

**Follow-up: Would caching help?**
A: Yes — frequently requested dashboard metrics could be cached to reduce repeated database queries.

**Q119: If there are 10 million session actions, what becomes slow?**
A: Operations that scan or aggregate very large numbers of session actions may slow down without appropriate indexing or partitioning.

**Follow-up: How would you solve it?**
A: Partition the table, maintain suitable indexes, archive older data, and optimize queries that access recent records most frequently.

**Q120: Explain your complete database design.**
A:

```
attackers ──1:N── sessions ──1:N── session_actions
```

The attackers table stores persistent attacker profiles, sessions stores each SSH connection, and session_actions stores the chronological timeline of events within each session. This normalized structure minimizes duplication and supports efficient querying, replay, and reporting.

**Follow-up: Why is this schema good for SOC analysis?**
A: Analysts investigate at different levels — attacker level (who?), session level (when?), action level (what exactly happened?) — and separating the data into related tables makes those investigations efficient and easy to query.

---

### Batch 6 Key Concepts Checklist

- ✅ PostgreSQL vs MongoDB — relational fits the data model
- ✅ 3 tables: attackers / sessions / session_actions (1:N, 1:N)
- ✅ Foreign keys + cascading delete
- ✅ Normalization → 3NF
- ✅ Indexes, ACID (durability), UPSERT / ON CONFLICT
- ✅ Dashboard queries via FastAPI, never direct browser access
- ✅ Performance: partitioning, archiving, read replicas, caching

---

## Batch 7 — FastAPI, Dashboard & Docker (Questions 121–140) ⭐⭐⭐⭐☆

> **Why interviewers care:** Tests backend fundamentals — async vs sync, connection pooling, API design, and deployment knowledge with Docker Compose.

### FastAPI & The Dashboard

**Q121: Why did you choose FastAPI?**
A: Native asynchronous support, high performance, automatic request validation, and clean integration with AsyncIO and async PostgreSQL drivers. Since the rest of CruxTrap uses async programming, FastAPI was a natural fit for the dashboard service.

**Follow-up: Why not Flask?**
A: Flask is excellent, but async support is not as natural as FastAPI's. The project already uses async throughout the stack, so FastAPI integrates more cleanly.

**Q122: What is FastAPI's role in CruxTrap?**
A: The dashboard backend — accept browser requests, query PostgreSQL, render HTML with Jinja2, serve static CSS/JS, and provide the `/api/stats` JSON endpoint. It does not communicate directly with attackers.

**Follow-up: Does FastAPI receive SSH connections?**
A: No. Only the SSH Honeypot handles attacker connections.

**Q123: Explain the request flow when a user opens the dashboard.**
A:

```
Browser → FastAPI → PostgreSQL → Query Results → Jinja2 Template → HTML → Browser
```

The browser sends an HTTP request; FastAPI executes SQL queries against PostgreSQL; results are rendered into HTML via Jinja2 and returned.

**Follow-up: Does FastAPI query Redis?**
A: No. The dashboard reads from PostgreSQL.

**Q124: Why use Jinja2?**
A: It's a server-side templating engine — FastAPI passes data into templates that generate complete HTML pages dynamically, instead of manually building HTML strings.

**Follow-up: Could React replace Jinja2?**
A: Yes — React could provide a client-side frontend — but the implemented project uses Jinja2 for server-side rendering.

**Q125: What API endpoints does your application expose?**
A: `/` (overview), `/sessions`, `/sessions/{session_id}`, `/attackers`, `/attackers/{ip}`, `/rl`, and `/api/stats`. Each route queries PostgreSQL and returns HTML or JSON.

**Follow-up: Which endpoint returns JSON?**
A: `/api/stats`.

**Q126: Why is /api/stats useful?**
A: It lets frontend JavaScript refresh dashboard statistics without reloading the entire page.

**Follow-up: What updates periodically?**
A: The dashboard metrics shown on the overview page.

### Async & Connection Pooling

**Q127: Why use asynchronous database access?**
A: It allows FastAPI to handle other requests while waiting for PostgreSQL — improving throughput and scalability under concurrent users.

**Follow-up: What happens during a blocking database query?**
A: A synchronous implementation would block the worker until the query finishes, reducing concurrency.

**Q128: What is a connection pool?**
A: A reusable set of database connections — instead of opening a new PostgreSQL connection per request, FastAPI borrows an existing one from the pool.

**Follow-up: Why is pooling faster?**
A: Creating database connections is expensive; reusing existing connections reduces latency and improves performance.

**Q129: What happens if multiple users open the dashboard simultaneously?**
A: FastAPI handles multiple requests concurrently — each acquires a database connection from the pool and processes independently.

**Follow-up: Does every request create a new PostgreSQL connection?**
A: No. Connections are reused through the pool.

### Docker & Docker Compose

**Q130: What is Docker?**
A: A containerization platform that packages an application with its runtime, dependencies, and configuration so it behaves consistently across environments.

**Follow-up: Why not install everything directly on the host?**
A: Docker eliminates dependency conflicts and makes deployment reproducible across development and production.

**Q131: Why Docker Compose?**
A: It defines all project services in one config file — a single command starts PostgreSQL, Redis, SSH Honeypot, Pipeline, and FastAPI, along with networking, volumes, and service dependencies.

**Follow-up: How many services are defined?**
A: Five.

**Q132: What services run in Docker?**
A: PostgreSQL, Redis, SSH Honeypot, Pipeline, and FastAPI — each in its own container for isolation, allowing independent update, restart, and scaling.

**Follow-up: Why separate containers?**
A: Isolation — each service can be updated, restarted, or scaled independently.

**Q133: What is a Docker volume?**
A: Persistent storage outside the container filesystem. In CruxTrap, volumes preserve PostgreSQL data, Redis data, and RL state/SSH host key across container restarts.

**Follow-up: Why not store everything inside the container?**
A: Container filesystems are ephemeral — without volumes, important data would be lost when containers are recreated.

**Q134: What is the Docker network used for?**
A: Docker Compose creates a private bridge network — containers communicate internally instead of exposing every service publicly.

**Follow-up: Which services are publicly exposed?**
A: Only SSH (port 2222) and Dashboard (port 8000). PostgreSQL and Redis remain internal.

### Startup, Failure & Deployment

**Q135: Explain the startup sequence.**
A: PostgreSQL starts → Redis → SSH Honeypot → Pipeline → FastAPI. Dependencies ensure required services are available before dependent services launch.

**Follow-up: Why doesn't FastAPI start first?**
A: It depends on PostgreSQL — without the database, dashboard queries cannot succeed.

**Q136: What happens if PostgreSQL is still starting?**
A: Docker Compose waits for PostgreSQL's health check before starting dependent services.

**Follow-up: Why use health checks instead of only startup order?**
A: Startup order alone doesn't guarantee a service is actually ready to accept connections — health checks verify readiness.

**Q137: What is container isolation?**
A: Each container has its own filesystem, processes, and runtime environment — problems in one container are less likely to directly affect another.

**Follow-up: Can the FastAPI container access PostgreSQL?**
A: Yes. They communicate over the internal Docker network.

**Q138: How would you deploy CruxTrap to the cloud?**
A: Keep the containerized services and deploy with managed infrastructure — e.g., managed PostgreSQL, managed Redis, and container orchestration for app services — while maintaining the same logical architecture.

**Follow-up: Would the architecture change?**
A: No. The deployment platform changes, but service interactions remain the same.

**Q139: What happens if the FastAPI container crashes?**
A: The dashboard becomes unavailable until restart — but the SSH Honeypot keeps capturing, Redis keeps storing events, the Pipeline keeps processing, and PostgreSQL keeps storing. Only the monitoring interface is affected.

**Follow-up: Will attacker sessions stop?**
A: No. The honeypot operates independently of the dashboard.

**Q140: Explain the deployment architecture.**
A:

```
Docker Compose
   ├── PostgreSQL
   ├── Redis
   ├── SSH Honeypot
   ├── Pipeline
   └── FastAPI Dashboard
```

Each service runs in its own container, communicates over an internal Docker network, uses persistent volumes where required, and performs a dedicated role.

**Follow-up: What are the biggest advantages of this deployment?**
A: Reproducible deployments, service isolation, easier maintenance, independent scaling, simplified dependency management, and consistent development/production environments.

---

### Batch 7 Key Concepts Checklist

- ✅ FastAPI vs Flask — async fit
- ✅ Dashboard request flow: Browser → FastAPI → PostgreSQL → Jinja2 → HTML
- ✅ Routes incl. `/api/stats` (JSON), session replay, attacker profiles
- ✅ Async DB access + connection pooling
- ✅ Docker Compose: 5 services, health checks, volumes, bridge network
- ✅ Exposed ports: SSH 2222, Dashboard 8000
- ✅ Failure isolation (FastAPI crash doesn't stop collection)

---

## Batch 8 — Pipeline Deep Dive (Questions 141–160) ⭐⭐⭐⭐⭐

> **Why interviewers care:** Tests your understanding of the consumer side of the event-driven architecture — parsing, enrichment, upserts, acknowledgements, and failure handling. This is where "did you actually write this?" gets answered.

### Role & Responsibilities

**Q141: What is the Pipeline service?**
A: An independent backend service responsible for consuming attacker events from Redis Streams, enriching them with GeoIP information, updating PostgreSQL, and acknowledging processed messages. It separates event processing from attacker interaction.

**Follow-up: Why not process everything inside the SSH service?**
A: The SSH service must respond to attackers with minimal latency. Moving enrichment and database writes into a separate service prevents slow operations from affecting the interactive shell.

**Q142: What is the main responsibility of the Pipeline?**
A: Read events from Redis Streams → parse incoming event data → perform GeoIP enrichment → update attacker records → update session records → store session actions → acknowledge processed messages.

**Follow-up: Does it execute attacker commands?**
A: No. It only processes events that have already occurred.

**Q143: Explain the Pipeline flow.**
A:

```
Redis Stream → Read Event → Parse JSON → GeoIP Lookup
→ Update Attacker → Update Session → Insert Session Action → ACK Message
```

**Follow-up: Where is PostgreSQL used?**
A: During the update and insert operations after enrichment.

**Q144: Why is the Pipeline asynchronous?**
A: It continuously waits for new events without blocking — AsyncIO handles I/O operations like Redis reads, GeoIP lookups, and PostgreSQL writes efficiently.

**Follow-up: Would multithreading also work?**
A: It could, but async programming is a natural fit for this I/O-heavy workload and avoids the overhead of many threads.

**Q145: What happens when a new Redis event arrives?**
A: The Pipeline receives it via XREADGROUP, parses it, enriches it, updates PostgreSQL, and finally acknowledges it.

**Follow-up: Is the event immediately deleted from Redis?**
A: No. It is acknowledged after successful processing according to the implemented flow.

### Parsing & Enrichment

**Q146: Why parse JSON?**
A: The event payload is stored as structured data. The Pipeline converts it into usable Python objects so fields like username, password, command, and session ID can be extracted.

**Follow-up: Why not store raw strings?**
A: Structured data is much easier to process, query, and extend than free-form text.

**Q147: What enrichment does the Pipeline perform?**
A: GeoIP enrichment — adding location info like country and city based on the attacker's source IP.

**Follow-up: Does it call external threat-intelligence APIs?**
A: No. The implemented Pipeline performs GeoIP enrichment only.

**Q148: Why perform GeoIP lookup?**
A: Location information helps analysts understand where attacks originate and identify geographic attack patterns.

**Follow-up: Does GeoIP identify the attacker?**
A: No. It estimates the geographic location of the IP address, not the individual's identity.

**Q149: What happens after enrichment?**
A: The Pipeline updates the `attackers`, `sessions`, and `session_actions` tables in PostgreSQL.

**Follow-up: Why not write everything into one table?**
A: The normalized schema reduces redundancy and supports efficient analysis.

### Database Operations

**Q150: What is upsert_attacker()?**
A: Inserts a new attacker if the IP has never been seen; otherwise updates the existing attacker record with the latest information.

**Follow-up: Why use UPSERT instead of INSERT?**
A: Because the same attacker may reconnect multiple times.

**Q151: What is upsert_session()?**
A: Creates or updates the session record for a specific session ID, keeping session metadata synchronized as new events arrive.

**Follow-up: Can one session receive multiple updates?**
A: Yes. Connection, login, commands, and disconnect events all contribute information during the session lifecycle.

**Q152: What is insert_action()?**
A: Records every individual action during a session — login, command execution, disconnect — each becoming a row in `session_actions`.

**Follow-up: Why not store commands inside the sessions table?**
A: A session can contain many commands, making a separate one-to-many table the correct relational design.

**Q153: How is event ordering maintained?**
A: The Pipeline records an `action_seq` value for each session action so events can be replayed in chronological order.

**Follow-up: Why is ordering important?**
A: Analysts must understand the exact sequence of attacker behavior during session replay.

### Failure Handling

**Q154: What happens if JSON parsing fails?**
A: The Pipeline catches the parsing error and falls back to an empty structure rather than crashing the entire service.

**Follow-up: Why is exception handling important?**
A: A single malformed event should not stop processing for all future events.

**Q155: How does the Pipeline know which session an event belongs to?**
A: Each event includes a session ID — the Pipeline uses it to update the correct session and associate actions with it.

**Follow-up: Why not use only the IP address?**
A: One attacker IP can have multiple independent SSH sessions.

**Q156: What happens if PostgreSQL becomes unavailable?**
A: Database operations fail, and the Pipeline's connection management logic retries connections according to its retry strategy before continuing when the database becomes available again.

**Follow-up: Does the SSH Honeypot stop?**
A: No. The SSH service continues independently because it is decoupled from PostgreSQL.

**Q157: Why acknowledge events only after processing?**
A: Acknowledging after processing ensures successfully handled events are marked complete only after the required work has finished.

**Follow-up: What if you acknowledged before processing?**
A: If processing failed afterward, the system could incorrectly consider the event complete even though it had not been stored.

### Scaling & Redesign

**Q158: How does the Pipeline improve scalability?**
A: The honeypot and database are separated by Redis Streams, allowing event generation and event processing to scale independently.

**Follow-up: Can multiple Pipeline instances run?**
A: Yes. The implementation uses Redis Consumer Groups, which support distributing messages across multiple consumers.

**Q159: Explain the complete Pipeline lifecycle.**
A:

```
Redis Event → Consume → Parse → GeoIP → UPSERT Attacker
→ UPSERT Session → INSERT Action → ACK → Wait for Next Event
```

**Follow-up: Which step is computationally expensive?**
A: Database operations and GeoIP lookups are generally more expensive than simple event parsing.

**Q160: If you were redesigning the Pipeline, what improvements would you make?**
A: Batch database writes, metrics and monitoring, dead-letter queue support, more robust retry handling, better observability, additional enrichment modules, and horizontal scaling with multiple workers — all while keeping the event-driven architecture.

**Follow-up: Would you change the overall architecture?**
A: No. The separation of SSH honeypot, Redis Streams, Pipeline, PostgreSQL, and FastAPI is sound — I would improve reliability, observability, and scalability rather than replace the core design.

---

### Batch 8 Key Concepts Checklist

- ✅ Pipeline role: consume → parse → enrich → upsert → insert → ACK
- ✅ Async I/O fit for the consumer workload
- ✅ GeoIP enrichment only (no external threat-intel APIs)
- ✅ upsert_attacker / upsert_session / insert_action semantics
- ✅ action_seq for chronological replay
- ✅ Failure handling: JSON fallback, retries, ACK-after-processing
- ✅ Consumer Groups → horizontal scaling

---

## Batch 9 — Fake File System & Command Processor (Questions 161–180) ⭐⭐⭐⭐☆

> **Why interviewers care:** Tests the deception core — how realism is achieved safely, how commands are simulated, and the separation between the filesystem and command logic.

### Fake File System — Why & Isolation

**Q161: Why did you implement a Fake File System?**
A: It makes the honeypot appear like a real Ubuntu server. Attackers expect directories like `/etc`, `/home`, `/var`, `/proc`. Instead of exposing the host OS, the honeypot generates an in-memory filesystem that safely mimics a Linux environment.

**Follow-up: Why not expose the real filesystem?**
A: That would be a serious security risk — an attacker could modify files, steal sensitive information, or damage the host. The fake filesystem provides realism while maintaining isolation.

**Q162: Is the Fake File System stored on disk?**
A: No. It exists only in memory during a session — created when the attacker connects, discarded when the session ends.

**Follow-up: Why is this better?**
A: Isolation between sessions, no persistence of attacker changes, and every session starts from a clean state.

**Q163: Does every attacker get the same filesystem?**
A: No. Each session gets its own `FakeFileSystem` instance — actions in one session never affect another.

**Follow-up: Can two attackers see each other's files?**
A: No. Each session has an isolated in-memory filesystem.

### Realistic Content

**Q164: Which directories are emulated?**
A: Realistic Linux directories: `/etc`, `/home`, `/root`, `/usr`, `/var`, `/proc`, `/tmp`, `/bin`, `/boot`, `/dev` — plus realistic files like `/etc/passwd`, `/etc/shadow`, `.bash_history`, SSH keys, and config files.

**Follow-up: Why create these directories?**
A: Attackers commonly inspect these locations during reconnaissance — their presence makes the honeypot more believable.

**Q165: What is inside /etc/passwd?**
A: A fake version resembling a real Linux system — looks realistic but doesn't correspond to actual system accounts.

**Follow-up: Why fake this file?**
A: Attackers frequently inspect `/etc/passwd` to identify users and targets; believable fake content encourages natural attacker behavior.

**Q166: Why include a fake /etc/shadow?**
A: Many attackers attempt to access password hashes after gaining shell access. Realistic-looking fake hashes keep the environment believable while protecting the host.

**Follow-up: Are these real password hashes?**
A: No. They are generated fake hashes designed only to simulate a real system.

**Q167: Why include fake SSH keys?**
A: Attackers often search for SSH keys to establish persistence or pivot. Fake keys encourage continued interaction without exposing real credentials.

**Follow-up: Could the attacker use these keys?**
A: No. They are fake and have no access to real systems.

**Q168: Why include .bash_history?**
A: Attackers inspect shell history to learn about admin activity or discover useful commands. A fake history increases realism and adds deception.

**Follow-up: Why not leave it empty?**
A: An empty history looks suspicious — realistic command history makes the environment appear genuine.

### Command Processor

**Q169: What is the Command Processor?**
A: The `CommandProcessor` interprets attacker commands and generates appropriate simulated responses. It does not execute commands on the host OS.

**Follow-up: Does it call /bin/ls?**
A: No. It simulates the behavior internally.

**Q170: Explain the command execution flow.**
A:

```
Attacker Types Command → Read Input → Parse Command
→ RL Agent Chooses Action → CommandProcessor
→ Generate Simulated Output → Display Output → Emit Redis Event
```

**Follow-up: Who decides the RL action?**
A: The Q-learning agent. The CommandProcessor only carries out the chosen behavior.

**Q171: How are commands parsed?**
A: The CommandProcessor parses attacker input, identifies the command and its arguments, and dispatches to the appropriate handler function.

**Follow-up: Why parse arguments?**
A: `cat /etc/passwd` and `cat /etc/shadow` perform different operations, so arguments must be interpreted correctly.

**Q172: Which Linux commands are supported?**
A: Around fifty commonly used commands: `ls`, `pwd`, `whoami`, `hostname`, `id`, `cat`, `ps`, `top`, `netstat`, `ss`, `ifconfig`, `ip`, `history`, `df`, `du`, `free`, `wget`, `curl`, `find`, `grep`, `chmod`, `rm`, `mkdir`, `sudo`, `exit` — all simulated, never executed on the host.

**Follow-up: Why only around fifty commands?**
A: These cover the commands attackers most commonly use during reconnaissance, privilege escalation, and post-exploitation — while keeping the implementation manageable.

**Q173: What happens when an unsupported command is entered?**
A: The CommandProcessor returns a realistic Linux-style `command not found` response and keeps the session active.

**Follow-up: Why not crash?**
A: A crash would immediately reveal that the environment is unstable or fake.

**Q174: Does the CommandProcessor modify the host system?**
A: No. All operations are simulated within the fake filesystem.

**Follow-up: Can `rm -rf /` damage your computer?**
A: No. It only affects the in-memory simulated environment and has no impact on the host OS.

### Command Implementation Details

**Q175: How is `cat /etc/passwd` handled?**
A: The CommandProcessor looks up the requested file in the FakeFileSystem and returns the stored fake content rather than reading the host's actual file.

**Follow-up: Does it use Python's `open()` on the real filesystem?**
A: No. It retrieves data only from the in-memory FakeFileSystem.

**Q176: How is `ls` implemented?**
A: The CommandProcessor queries the FakeFileSystem for the current directory's contents and formats the result to resemble real `ls` output.

**Follow-up: Does it read real directories?**
A: No. It only lists directories from the simulated filesystem.

**Q177: Why is the filesystem procedural?**
A: It is generated programmatically per session rather than stored as static files — consistent structure, per-session isolation, and realistic content generation.

**Follow-up: Why not ship a complete disk image?**
A: A procedural approach is lighter, easier to maintain, and avoids exposing unnecessary real system artifacts.

### Deception & Component Separation

**Q178: How does the Fake File System improve deception?**
A: Attackers behave more naturally when the environment resembles a genuine Linux server — realistic directories, config files, SSH keys, logs, and shell history encourage continued interaction and make detection less likely.

**Follow-up: What happens if an attacker realizes it's fake?**
A: They may change their behavior or disconnect, reducing the value of the collected telemetry.

**Q179: How does the CommandProcessor interact with the RL agent?**
A: The RL agent decides the response (ALLOW, DELAY, FAKE, INSULT, BLOCK); the CommandProcessor executes that decision by generating the appropriate simulated response.

**Follow-up: Does the CommandProcessor perform learning?**
A: No. Learning is handled entirely by the Q-learning agent.

**Q180: Explain the complete Fake File System and CommandProcessor workflow.**
A:

```
SSH Session Starts → FakeFileSystem Created → Ubuntu-like Structure Generated
→ Attacker Enters Command → Command Parsed → RL Agent Selects Action
→ CommandProcessor Executes Simulated Response → Output Returned to Attacker
→ Event Sent to Redis → Pipeline Processes Event
```

**Follow-up: Why separate the FakeFileSystem from the CommandProcessor?**
A: Single responsibility — FakeFileSystem manages simulated files/directories; CommandProcessor interprets commands and produces responses using the filesystem. This improves modularity, testing, and maintainability.

---

### Batch 9 Key Concepts Checklist

- ✅ In-memory, per-session, isolated filesystem (never on disk)
- ✅ Realistic dirs + files: `/etc/passwd`, `/etc/shadow`, SSH keys, `.bash_history`
- ✅ ~50 simulated commands — no host execution
- ✅ Unknown commands → `command not found`, never crash
- ✅ `cat`/`ls` read from FakeFileSystem, not real filesystem
- ✅ Procedural generation vs disk image
- ✅ Separation: FakeFileSystem (state) / CommandProcessor (behavior) / RL (decisions)

---

## Batch 10 — System Design, Scalability & Production (Questions 181–200) ⭐⭐⭐⭐⭐

> **Why interviewers care:** The final exam — bottlenecks, scaling, security trade-offs, and how you think about production readiness. Honest answers about limitations score higher than overclaiming.

### Bottlenecks & Scaling

**Q181: What is the biggest bottleneck in your current architecture?**
A: The Pipeline. Every attacker event must pass through it before reaching PostgreSQL — Redis reads, GeoIP lookup, database writes, and ACK operations make it the limiting factor under high attack volume.

**Follow-up: How would you solve it?**
A: Run multiple Pipeline instances within the same Redis Consumer Group so events are distributed across workers.

**Q182: Can your architecture handle 10,000 attackers?**
A: Not in its current form — it's a portfolio-scale system. Supporting 10,000 concurrent attackers would need multiple SSH honeypot instances, multiple Pipeline workers, Redis Cluster, PostgreSQL partitioning, and load balancing.

**Follow-up: Which component fails first?**
A: The SSH honeypot and Pipeline — session handling and event processing are the primary bottlenecks.

**Q183: How would you horizontally scale the SSH Honeypot?**
A: Deploy multiple honeypot instances behind a load balancer; each manages its own sessions while publishing into the same Redis infrastructure.

**Follow-up: Would attackers notice?**
A: No. Each SSH session stays bound to the instance that accepted it, so the interaction remains consistent.

**Q184: How would you scale PostgreSQL?**
A: Read replicas for dashboard traffic, table partitioning for large datasets, additional indexes, connection pooling, and archiving historical data.

**Follow-up: Would sharding be your first choice?**
A: No. I'd first optimize indexing and partitioning — simpler and often sufficient before introducing sharding complexity.

**Q185: Why not store everything in Redis?**
A: Redis is for fast in-memory messaging; PostgreSQL is for durable relational storage, historical analysis, joins, and complex queries. They solve different problems.

**Follow-up: Can Redis permanently replace PostgreSQL?**
A: Not for this project. Long-term investigation and reporting require relational storage.

### Failure Scenarios & High Availability

**Q186: What happens if Redis crashes?**
A: The SSH service cannot publish new events successfully and the Pipeline cannot consume additional messages until Redis is restored. The dashboard continues displaying previously stored data from PostgreSQL.

**Follow-up: Will existing dashboard data disappear?**
A: No. Historical data already stored in PostgreSQL remains available.

**Q187: What happens if PostgreSQL crashes?**
A: The Pipeline cannot persist new events and the dashboard cannot load new or historical data until PostgreSQL is restored. The honeypot keeps accepting sessions because it doesn't depend directly on PostgreSQL.

**Follow-up: Can attackers still interact with the honeypot?**
A: Yes. The SSH service continues independently.

**Q188: How would you make the system highly available?**
A: Multiple SSH honeypots, Redis replication or clustering, multiple Pipeline workers, PostgreSQL high availability, a load balancer, and health monitoring.

**Follow-up: Would Docker Compose still be enough?**
A: No. For high availability I'd move to a container orchestration platform such as Kubernetes.

### Architecture Principles & Security

**Q189: Why choose a microservice-style architecture?**
A: Each service has one responsibility — making the system easier to maintain, independently scalable, easier to debug, and easier to replace.

**Follow-up: Could this project be a monolith?**
A: Yes — a smaller deployment could be a monolith — but separating responsibilities improves modularity and scalability.

**Q190: Explain the Single Responsibility Principle in your project.**
A: Every service has one purpose — SSH Honeypot captures attackers, Pipeline processes events, Redis transports events, PostgreSQL stores data, FastAPI presents data.

**Follow-up: Why is this beneficial?**
A: Changing one component is less likely to affect the others.

**Q191: How would you secure the dashboard?**
A: User authentication, role-based access control, HTTPS, secure session management, and audit logging. The current implementation intentionally focuses on monitoring functionality and doesn't include these production features.

**Follow-up: Would basic authentication be enough?**
A: For production, I'd prefer stronger authentication with proper user management and authorization rather than only basic auth.

**Q192: How would you monitor this application?**
A: Service health, Redis throughput, PostgreSQL performance, pipeline lag, CPU, memory, disk usage, and container health.

**Follow-up: What metric is most important?**
A: Pipeline lag — it indicates whether events are accumulating faster than they're being processed.

**Q193: How would you deploy this project in AWS?**
A: Containers for application services, managed PostgreSQL, managed Redis, a load balancer, private networking, and secure dashboard access — the logical architecture stays the same.

**Follow-up: Would Docker Compose run in production?**
A: It suits development and small deployments; production typically uses orchestration and managed infrastructure.

**Q194: What security risks exist in the current implementation?**
A: Dashboard authentication is not implemented, captured credentials are intentionally stored plaintext (part of honeypot design), and additional production hardening is needed — known trade-offs of a portfolio implementation.

**Follow-up: Would you deploy this directly to the Internet?**
A: Not without adding authentication, HTTPS, operational monitoring, and other production hardening measures.

**Q195: What would you improve first?**
A: Dashboard authentication, better monitoring and observability, more robust retry/recovery, horizontal scaling, and additional enrichment modules.

**Follow-up: Why authentication first?**
A: Protecting analyst access is a fundamental security requirement before adding additional functionality.

### Final Answers & Personal Branding

**Q196: Why use asynchronous programming?**
A: Most operations are I/O-bound — async lets services keep processing while waiting on Redis, PostgreSQL, or network operations.

**Follow-up: Would multithreading be faster?**
A: Not necessarily. For I/O-heavy workloads, async is often simpler and more resource-efficient.

**Q197: Explain your architecture in one minute.**
A: CruxTrap has five services. The AsyncSSH Honeypot captures attacker interactions and publishes events to Redis Streams. A Pipeline consumes those events, enriches them with GeoIP, and stores them in PostgreSQL. FastAPI queries PostgreSQL to render a SOC-style dashboard where analysts investigate attackers, sessions, and command history. Each service has a single responsibility, keeping the system modular and maintainable.

**Follow-up: Which service is the most important?**
A: The SSH Honeypot — it is the source of all attacker telemetry.

**Q198: If you started over, would you change the architecture?**
A: The core architecture is solid. I'd keep the same separation of responsibilities but enhance operational aspects — monitoring, authentication, scalability — rather than redesign.

**Follow-up: Would you still use Redis?**
A: Yes. Redis Streams remain a good fit for decoupling event generation from processing here.

**Q199: What did you learn from building this project?**
A: Event-driven architecture, async Python, SSH protocol handling, reinforcement learning integration, Redis Streams, PostgreSQL design, Docker deployment, and designing secure, realistic deception systems.

**Follow-up: What was the hardest part?**
A: Coordinating the interaction between the SSH honeypot, RL decision logic, Redis event streaming, and persistence pipeline while keeping the architecture modular.

**Q200: Why should we hire you based on this project?**
A: It demonstrates more than programming — combining cybersecurity concepts, distributed systems, async backend development, databases, Docker, and machine learning into one integrated system. I designed it, understand how the components interact, how data flows through it, and how it could scale — which translates directly to real security engineering and backend work.

**Follow-up: What does this project prove about you?**
A: That I can design, implement, and explain a complete end-to-end security platform — not just isolated code. I understand both the implementation details and the architectural trade-offs.

---

### Batch 10 Key Concepts Checklist

- ✅ Biggest bottleneck: Pipeline — scale with Consumer Groups
- ✅ 10k attackers needs: multi-honeypot, multi-pipeline, Redis Cluster, partitioning
- ✅ Failure independence: Redis down / PostgreSQL down scenarios
- ✅ HA path: Kubernetes + managed infrastructure
- ✅ SRP mapping across the 5 services
- ✅ Honest security limitations (no auth, plaintext creds by design)
- ✅ Pipeline lag = most important metric
- ✅ "One-minute architecture" answer rehearsed

---

## Full Question Index (1–200)

| Batch | Topic | Questions | Difficulty |
|---|---|---|---|
| 1 | Project Overview & Concepts | 1–20 | ⭐⭐⭐ |
| 2 | Architecture | 21–40 | ⭐⭐⭐⭐ |
| 3 | SSH Honeypot + AsyncSSH | 41–60 | ⭐⭐⭐⭐ |
| 4 | Reinforcement Learning | 61–80 | ⭐⭐⭐⭐⭐ |
| 5 | Redis & Event-Driven Architecture | 81–100 | ⭐⭐⭐⭐ |
| 6 | PostgreSQL & Database Design | 101–120 | ⭐⭐⭐⭐ |
| 7 | FastAPI, Dashboard & Docker | 121–140 | ⭐⭐⭐⭐ |
| 8 | Pipeline Deep Dive | 141–160 | ⭐⭐⭐⭐⭐ |
| 9 | Fake File System & Command Processor | 161–180 | ⭐⭐⭐⭐ |
| 10 | System Design, Scalability & Production | 181–200 | ⭐⭐⭐⭐⭐ |

## Final Study Plan

1. **Week 1** — Master the 1-minute summary + Batch 1 (overview). Recite Q40 and Q197 out loud until they flow.
2. **Week 2** — Batches 2–3 (architecture + SSH honeypot). Draw the diagrams from memory.
3. **Week 3** — Batch 4 (RL). Practice explaining the Q-learning equation by hand. This is your differentiator.
4. **Week 4** — Batches 5–8 (Redis, PostgreSQL, FastAPI, Pipeline). Focus on failure scenarios and Redis commands (XADD, XREADGROUP, XACK, PEL).
5. **Week 5** — Batches 9–10 + full mock interview. Get comfortable answering follow-ups.
6. **Day before interview** — Re-read the One-Minute Summary, architecture diagram, and the "Final Answers" section (Q197–200).

---

## Interview Tips

1. **Start strong:** Memorize the "One-Minute Summary" — it covers the whole system in 20 seconds.
2. **Know your trade-offs:** Be ready to justify every choice (Redis vs direct DB, PostgreSQL vs MongoDB, FastAPI vs Flask, Q-learning vs supervised).
3. **Speak security-first:** Emphasize the fake filesystem, fake environment, and why attackers can't reach the real OS.
4. **Have an answer for "most proud of":** The RL + SSH integration — it shows ownership and innovation.
5. **Roadmap = ambition:** Mentioning dashboard auth first shows you think like a security engineer (security of your own tools).
6. **Expect depth questions:** Be ready for "What's a Q-value?", "How do Redis Streams differ from Pub/Sub?", "How would you scale the pipeline?" — study these if not covered above.
