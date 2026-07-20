# Grandmate — 10 Minute Demo Script

Two parts of five minutes each, so they can be recorded separately and re-recorded independently.

**How to use this:** the *Show* column is what should be on screen. The **>** blocks are what to
say — spoken language, not written English, so read them aloud once before recording. Say numbers
slowly; they are carrying a lot of weight in this story.

**Tone:** calm and confident. Explain like you are sitting next to a friend who plays chess but
does not know anything about AI. No jargon unless you immediately explain it in plain words.

---

# Part 1 — The Problem, The Product, The Design (5:00)

## 0:00 – 1:15 · What is the problem, and why does it matter

**Show:** The landing page, cursor resting on the input box. Stay here. Do not click yet.

> "Hello everyone, I am Rakesh, and I would like to show you something we have built called
> **Grandmate** — think of it as your grandmaster mate.
>
> Let me start with a problem that almost every chess player has faced.
>
> Today, roughly ten million games of chess are played online every single day. And after your
> game finishes, every chess site will offer you the same thing — click one button, and a computer
> engine will analyse your game.
>
> Now what does that analysis actually give you? It gives you a graph that goes up and down. It
> gives you numbers like *minus one point four*. And it tells you 'move twenty-seven was an
> inaccuracy'.
>
> All of that is completely correct. And for most players, it is completely useless.
>
> Because the engine tells you **what** happened. It never tells you **why**. It will not tell you
> that you let go of the centre. It will not tell you that you walked into a fork. And it certainly
> will not tell you what you should practise before your next game.
>
> That gap — between a correct number and an actual lesson — is the gap a human coach fills. But a
> good coach costs money, and needs to be booked, and is simply not available to most players.
>
> So the question we asked was very simple. Can we take the engine's correctness, and add the
> coach's explanation on top of it? That is exactly what Grandmate does."

## 1:15 – 2:00 · Why this is genuinely hard

**Show:** Stay on the landing page.

> "Now, you might be thinking — this sounds easy. Just take the engine output and ask a language
> model to explain it.
>
> But there is a serious problem with that. Language models hallucinate. And in chess, a
> hallucination is not a small mistake. If the coach confidently tells you 'you should have played
> knight to f6' — and that move is **not even legal** in that position — you have not just given
> bad advice. You have taught the student something wrong. They will trust it, and they will lose
> games because of it.
>
> So our number one rule became this: **the language model is never allowed to analyse a chess
> position.** Not once. All the chess facts come from the engine. The model's only job is to
> explain those facts in human language.
>
> Everything you are about to see is built around that one rule."

## 2:00 – 3:30 · The product, working

**Show:** Paste a real game (or pick from the sample dropdown). Click Analyse. Let it run. Then
scroll through the report as you talk.

> "So let me actually show you. I am pasting one of my own games here, and clicking analyse.
>
> While this runs, here is what is happening behind the scenes. The game is being parsed. A real
> chess engine — Stockfish — is going through every single move and calculating how much each move
> cost you. And then our coaching layer is turning that into an explanation.
>
> And here is the report.
>
> First, an **overview** — how the game actually went. Then **what went well** — and I want you to
> notice this, because most tools only tell you what you did wrong. This one names the specific good
> moves and tells you why they worked.
>
> Then **the mistakes**. Look at the detail here — it gives you the move number, the move you
> played, what it cost you, the better move, *and* why that move was better. That last part is the
> whole point. 'Play d4 instead' is information. 'Play d4, because it opens lines for your pieces'
> is a lesson.
>
> And finally, **what to work on** — drawn from the mistakes in this actual game, not generic advice
> like 'study more openings'."

## 3:30 – 4:15 · Ask it questions

**Show:** Type a follow-up in the chat panel — *"why was that move a blunder?"* — send it. Then
type something off-topic like *"who won the football world cup?"* to show the refusal.

> "Now, a report is one-way. Real coaching is a conversation. So you can just ask.
>
> [after the answer] Notice it is still talking about *this* game, and *these* moves. It has not
> drifted into general chess theory.
>
> And let me show you one more thing quickly. If I ask it something that has nothing to do with
> chess — it politely refuses. It stays in its lane. For a coaching tool, that boundary matters."

## 4:15 – 5:00 · How it is built, in one breath

**Show:** `docs/ARCHITECTURE.md` §4 — the router and specialists diagram.

> "Very quickly, how this is put together — because it is not one big AI doing everything.
>
> It is a small team. A **router** reads your question and decides who should answer. A **strategy
> specialist** handles tactics and plans. A **rules specialist** handles the laws of chess. And a
> **coach** combines their work into the single answer you read.
>
> And the router is deliberately cheap. When you ask for a game review, it makes **zero** extra AI
> calls to make that decision — it already knows. It only thinks when you ask something genuinely
> new in the chat.
>
> One more thing worth seeing — this panel here. Every single AI step is recorded and shown to you:
> what was asked, what came back, which documents were used. Nothing is hidden.
>
> In part two, I will show you the retrieval system behind this, and how we tested all of it
> honestly."

---

# Part 2 — Advanced Retrieval, and Honest Evaluation (5:00)

## 5:00 – 6:15 · Why we split the library into two

**Show:** Developer Insights → **RAG** tab, showing a retrieved chunk and its source.

> "Welcome back. This part is where most of our engineering effort actually went.
>
> The coach needs knowledge — opening ideas, tactical patterns, and the official laws of chess. So
> we built a library. But we did **not** put it all in one place, and that decision turned out to
> matter a lot.
>
> Think about it practically. If you ask *'was that castling legal?'*, you need the FIDE rulebook.
> If you ask *'was castling a good idea there?'* — the rulebook is useless. You need strategy
> material.
>
> Same word. Completely different question.
>
> So we keep two separate shelves — one for **rules**, one for **strategy** — and before we search
> at all, we decide which shelf to look on.
>
> And here is the number that justifies it. We measured search quality with and without this split,
> across one hundred and thirty-five test questions.
>
> Without the split, our ranking score was **0.71**. With the split, the same system scores
> **0.82**. That is a fifteen percent improvement — and we did not change the search algorithm at
> all. We only stopped searching in the wrong place."

## 6:15 – 7:15 · Two ways of searching, combined

**Show:** `docs/retriever_evaluation_report.md`, on the comparison table.

> "Now, the second piece. There are two ways to search a library, and both have a weakness.
>
> The first is **keyword search**. You search for the words that were typed. It is fast and it is
> exact — but if you ask about 'castling on the queen's side' and the book says 'long castling', it
> will find nothing.
>
> The second is **meaning-based search**. This one understands that those two phrases mean the same
> thing. But it can drift — it sometimes returns things that feel related but are not what you
> asked.
>
> So we run **both**, and then merge the two ranked lists into one.
>
> And here is the honest result. Look at this table. Meaning-based search alone gets **87%**.
> Keyword search alone gets **80%**. Our combined approach gets **85.6%** — so on raw hit rate, it
> is very slightly behind.
>
> But look at the ranking column. The combined approach scores **highest** — 0.817. And ranking is
> what actually matters here, because we only pass the top couple of results to the coach. Getting
> the *right* one at the *top* matters more than finding it somewhere in the list.
>
> We are showing you a number where we are not the winner on every column, because that is the
> honest picture."

## 7:15 – 8:15 · The safety net

**Show:** Developer Insights → **Grounding** tab.

> "Now let me come back to that first rule — the model is never allowed to invent a chess move.
>
> How do we actually enforce that? Every single move that appears in the coach's answer is pulled
> out and checked against a real chess rules engine. Is this move legal, in this exact position,
> right now?
>
> If a move does not pass, the answer is rejected and rewritten. The user never sees it.
>
> And the result of that check is: **zero percent**. Across our whole test set, not a single
> illegal or invented move has reached a user. That is not a claim about how good the model is. It
> is a guarantee, because the check is a rules engine, not another AI."

## 8:15 – 9:15 · How we caught our own tests lying

**Show:** `docs/Deliverables.md` §5 — the scorecard.

> "And that same habit — do not trust the first result, check it properly — is how we caught
> something quite embarrassing about ourselves.
>
> At one point our test scores were beautiful. Ninety-five percent, ninety-eight percent. Very nice
> to look at.
>
> Then we checked how those tests worked. And we found that the answer sheet was being written by
> the *same code* we were testing. So of course it agreed with itself. We were not measuring
> anything. We were just admiring our own reflection.
>
> So we rebuilt it. Now the answer key comes from a completely independent, much deeper engine
> analysis — a genuine second opinion.
>
> Our scores went **down**. Blunder detection is now **93%**, measured against that independent
> check across one hundred and fifty-one positions.
>
> And we did one more thing. We deliberately broke our own system, to check that the test would
> actually catch it. It did — the score collapsed from 95% to 19%. A test that cannot fail is not
> a test. Ours can fail. That, for me, is the most important slide in this whole demo."

## 9:15 – 10:00 · What is next, and thank you

**Show:** Back to the dashboard.

> "So where does this go next?
>
> The most important thing is memory. Right now, Grandmate remembers your conversation while you
> are using it — but if you come back next week, it starts fresh. The real value of a coach is that
> they remember you. They know you keep losing the same endgames. That is what we are building next.
>
> After that — pulling in your recent games and spotting patterns across all of them, not just one.
> And opponent preparation, so before a match you can see what your opponent struggles against.
>
> But the foundation is already here. Engine facts for correctness. A properly organised library
> for knowledge. A rules engine standing guard so nothing invented ever reaches you. And honest
> tests that are actually capable of telling us we are wrong.
>
> Thank you very much for watching."

---

## Recording notes

- **Warm the app up before recording.** The first request after starting the server is noticeably
  slower, because the search index and engine cache are still being built. Run one review, throw it
  away, then start recording.
- **Have the game ready.** Do not paste a long PGN on camera — use the sample dropdown, or paste it
  before you start speaking.
- **The numbers to say slowly:** 0.71 to 0.82, 93%, zero percent, 95% down to 19%.
- **If a number on screen disagrees with the script, trust the screen** and say the number you see.
  These figures move slightly between runs, because the chess engine is not perfectly reproducible
  under a time limit.
- **Do not claim the coaching-quality score.** It is currently measured on artificial single-move
  positions rather than real games, so the figure understates reality and inviting questions about
  it will cost you time you do not have.
