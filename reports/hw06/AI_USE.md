# HW6 AI use

**1. What I used an AI assistant for, and what I did myself**

I used AI for developing the MongoDB document API, the chat memory loop, the file-memory commands, the sweep script, and the draft of `METRICS.md`.

The document shape (an inspection with an embedded owner and violations, database `s1421_doc`) came from that. The screenshots and `report.pdf` are still mine to assemble, and I need to check the numbers in `METRICS.md` against `raw/short_term_sweep.csv`.

**2. One AI output that was wrong or unsuitable**

The first probe set asked for San Jose, Japanese food, a critical deduction of 8, and a follow-up. Those strings were already in `AGENT.md` or in the draft `MEMORY.md`. A model could score 5 on them without using the conversation at all, so the short-term comparison would have been meaningless.

**3. How I detected the problem**

Before the 30-message sweep, the probe strings were compared with the system prompt. `AGENT.md` says the project is in San Jose, and the draft memory file repeated the cuisine and the deduction. A two-turn test also showed the model arguing that Gilroy was "not a supported city" because the primer said San Jose.

**4. What I changed and why it works now**

The planted facts and the probes were changed to values that do not appear in the project files: Gilroy, Korean, Thursday, a deduction of 7, and Lantern Noodle at 91 with a return visit. The primer now says a personal fact overrides the project description. A later two-turn check answered "Gilroy" from the stored episode, and all four sweep settings scored 5.0 on the five probes, including N=4, whose window no longer holds the first messages.
