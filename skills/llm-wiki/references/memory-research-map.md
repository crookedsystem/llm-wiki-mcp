# Memory Research Map

Use this reference when justifying or changing the LLM Wiki memory taxonomy, adding or removing memory kinds, changing retrieval/write policy, or answering why the policy exists. Do not load it during ordinary prompt-time context injection.

## Table of Contents

- [Corpus Summary](#corpus-summary)
- [Research Axes](#research-axes)
- [Core Conclusions](#core-conclusions)
- [Policy Implications](#policy-implications)
- [Representative References](#representative-references)
- [When to Update This Map](#when-to-update-this-map)

## Corpus Summary

The current taxonomy was derived from a multi-agent research pass: 10 independent research tracks, 50 references per track, for 500 reviewed references, plus an arXiv candidate sweep with 862 filtered candidates. The full corpus should not be pasted into `SKILL.md`; this map preserves the conclusions and representative anchors so future agents can re-open the right research area on demand.

The 10 tracks were:

1. Cognitive science and human memory systems.
2. LLM agent long-term memory.
3. RAG, retrieval, indexing, and external memory.
4. Personalization, user modeling, and preference memory.
5. Continual learning, model editing, and catastrophic forgetting.
6. Knowledge graphs, semantic wikis, and provenance.
7. Procedural memory, tool use, and workflow learning.
8. Reflection, error prevention, and evaluation feedback.
9. Privacy, safety, retention, and governance.
10. Memory evaluation and long-context benchmarks.

## Research Axes

Human memory work separates working, episodic, semantic, and procedural memory. That separation maps cleanly to agent memory because each class has different durability, retrieval triggers, and failure modes.

Agent-memory work shows that useful long-term memory needs explicit operations: write, read, consolidate, forget, and reflect. Storing everything degrades retrieval quality and creates stale or unsafe context.

RAG and external-memory research shows that retrieval quality depends on chunking, indexing, ranking, query formation, and provenance. For LLM Wiki, `kb_context` should remain a scoped navigation layer, while `kb_search_notes` and full note reads provide evidence.

Personalization research supports storing explicit preferences and feedback, but warns against over-inference. Preference memory should be scoped, inspectable, and reversible.

Continual-learning and model-editing work highlights catastrophic forgetting, overfitting, and unintended generalization. LLM Wiki avoids weight updates; it should still prevent overgeneralized prompt memories through scope and review dates.

Knowledge graph and provenance work supports entity anchors, typed relationships, source records, confidence, and conflict tracking. This justifies putting memory on stable person/project/module/workflow/concept pages instead of loose note fragments.

Procedural memory and tool-use work supports saving reusable command sequences and workflows, especially when they reduce repeated reasoning or fragile tool usage.

Reflection and error-prevention work supports saving failures only when converted into future checks. The memory should be prevention-oriented, not blame-oriented.

Safety and governance work supports minimization, consent, provenance, retention, deletion workflows, and sensitive-data exclusions.

Memory evaluation work shows that success must be measured by future task utility, retrieval precision, contradiction handling, and staleness management, not memory volume.

## Core Conclusions

1. Store less than the transcript. A memory is useful only if it changes future behavior.
2. Separate memory kinds because durability and retrieval rules differ.
3. Scope every memory to the smallest stable owner.
4. Store explicit preferences and feedback; do not infer personality.
5. Store project conventions only when repo/service/module/path scope matches.
6. Convert repeated errors into prevention cues.
7. Keep provenance, confidence, conflicts, and review horizons with the cue.
8. Prefer updating or merging existing scoped pages over creating parallel memory pages.
9. Treat prompt-time memory as advisory. It never outranks current instructions or verified repo state.
10. Keep the detailed research in `references/`, not in the always-loaded skill body.

## Policy Implications

The LLM Wiki memory kinds intentionally combine cognitive-memory categories with agent-operational categories:

- Cognitive basis: `working_context`, `episodic_event`, `semantic_fact`, `procedural_pattern`.
- Personalization and local practice: `preference_profile`, `project_convention`.
- Governance and risk: `constraint_policy`, `provenance_signal`.
- Improvement loops: `failure_prevention`, `evaluation_feedback`.
- Future action: `prospective_task`.

The write policy follows a minimization principle: if a cue lacks future utility, stable scope, evidence, action effect, or reviewability, it should not become prompt-time memory.

The retrieval policy follows a precision principle: exact scope beats broad semantic similarity, and stale or snippet-only cues should be labeled rather than injected as commands.

## Representative References

These references are anchors for the 500+ item corpus. Use them to restart focused research instead of treating this list as exhaustive.

### Cognitive Memory

- Baddeley, A. D., and Hitch, G. J. "Working Memory." 1974. https://doi.org/10.1016/S0079-7421(08)60452-1
- Tulving, E. "Memory and Consciousness." 1985. https://doi.org/10.1037/0003-066X.40.4.385
- Squire, L. R. "Memory systems of the brain." 2004. https://doi.org/10.1016/j.nlm.2004.06.005
- Anderson, J. R. "ACT: A simple theory of complex cognition." 1996. https://doi.org/10.1037/0003-066X.51.4.355
- Schacter, D. L. "The seven sins of memory." 1999. https://doi.org/10.1037/0003-066X.54.3.182

### LLM Agent Memory

- Park et al. "Generative Agents: Interactive Simulacra of Human Behavior." 2023. https://doi.org/10.1145/3586183.3606763
- Packer et al. "MemGPT: Towards LLMs as Operating Systems." 2023. https://arxiv.org/abs/2310.08560
- Zhong et al. "MemoryBank: Enhancing Large Language Models with Long-Term Memory." 2023. https://arxiv.org/abs/2305.10250
- Wang et al. "Voyager: An Open-Ended Embodied Agent with Large Language Models." 2023. https://arxiv.org/abs/2305.16291
- Sumers et al. "Cognitive Architectures for Language Agents." 2023. https://arxiv.org/abs/2309.02427

### RAG and External Memory

- Lewis et al. "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." 2020. https://arxiv.org/abs/2005.11401
- Karpukhin et al. "Dense Passage Retrieval for Open-Domain Question Answering." 2020. https://arxiv.org/abs/2004.04906
- Izacard and Grave. "Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering." 2020. https://arxiv.org/abs/2007.01282
- Gao et al. "Retrieval-Augmented Generation for Large Language Models: A Survey." 2023. https://arxiv.org/abs/2312.10997
- Microsoft Research. "GraphRAG: From Local to Global." 2024. https://arxiv.org/abs/2404.16130

### Personalization and Preference Memory

- Salemi et al. "LaMP: When Large Language Models Meet Personalization." 2023. https://arxiv.org/abs/2304.11406
- Rafailov et al. "Direct Preference Optimization." 2023. https://arxiv.org/abs/2305.18290
- Christiano et al. "Deep Reinforcement Learning from Human Preferences." 2017. https://arxiv.org/abs/1706.03741
- Kirk et al. "Personalisation within Bounds." 2024. https://arxiv.org/abs/2402.00308
- OpenAI. "Model Spec." 2024. https://model-spec.openai.com/

### Continual Learning and Model Editing

- Kirkpatrick et al. "Overcoming catastrophic forgetting in neural networks." 2017. https://doi.org/10.1073/pnas.1611835114
- Lopez-Paz and Ranzato. "Gradient Episodic Memory for Continual Learning." 2017. https://arxiv.org/abs/1706.08840
- Mitchell et al. "Model Editing Networks with Gradient Decomposition." 2021. https://arxiv.org/abs/2110.11309
- Meng et al. "Locating and Editing Factual Associations in GPT." 2022. https://arxiv.org/abs/2202.05262
- Yao et al. "Editing Large Language Models: Problems, Methods, and Opportunities." 2023. https://arxiv.org/abs/2305.13172

### Knowledge Graphs, Wikis, and Provenance

- W3C. "PROV-O: The PROV Ontology." 2013. https://www.w3.org/TR/prov-o/
- Hogan et al. "Knowledge Graphs." 2021. https://doi.org/10.1145/3447772
- Bollacker et al. "Freebase: a collaboratively created graph database." 2008. https://doi.org/10.1145/1376616.1376746
- Vrandecic and Krotzsch. "Wikidata: a free collaborative knowledgebase." 2014. https://doi.org/10.1145/2629489
- Berners-Lee et al. "The Semantic Web." 2001. https://www.scientificamerican.com/article/the-semantic-web/

### Procedures, Tools, and Workflows

- Schick et al. "Toolformer: Language Models Can Teach Themselves to Use Tools." 2023. https://arxiv.org/abs/2302.04761
- Yao et al. "ReAct: Synergizing Reasoning and Acting in Language Models." 2022. https://arxiv.org/abs/2210.03629
- Shinn et al. "Reflexion: Language Agents with Verbal Reinforcement Learning." 2023. https://arxiv.org/abs/2303.11366
- Madaan et al. "Self-Refine: Iterative Refinement with Self-Feedback." 2023. https://arxiv.org/abs/2303.17651
- Patil et al. "Gorilla: Large Language Model Connected with Massive APIs." 2023. https://arxiv.org/abs/2305.15334

### Privacy, Safety, and Governance

- NIST. "Artificial Intelligence Risk Management Framework." 2023. https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf
- European Union. "General Data Protection Regulation." 2016. https://eur-lex.europa.eu/eli/reg/2016/679/oj
- Solove. "A Taxonomy of Privacy." 2006. https://doi.org/10.15406/mojcr.2017.05.00149
- OpenAI. "Preparedness Framework." 2023. https://openai.com/safety/preparedness/
- Nissenbaum. "Privacy in Context." 2009. https://www.sup.org/books/title/?id=8862

### Evaluation and Long Context

- Bai et al. "LongBench: A Bilingual, Multitask Benchmark for Long Context Understanding." 2023. https://arxiv.org/abs/2308.14508
- Wu et al. "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory." 2024. https://arxiv.org/abs/2410.10813
- Liu et al. "Lost in the Middle: How Language Models Use Long Contexts." 2023. https://arxiv.org/abs/2307.03172
- Kamradt. "Needle In A Haystack." 2023. https://github.com/gkamradt/LLMTest_NeedleInAHaystack
- Li et al. "LooGLE: Can Long-Context Language Models Understand Long Contexts?" 2023. https://arxiv.org/abs/2311.04939

## When to Update This Map

Update this map when:

- adding or removing a memory kind;
- changing retrieval precedence or write thresholds;
- introducing new privacy/safety retention rules;
- replacing the hook architecture;
- finding a benchmark or paper that changes the practical policy;
- a future research pass expands or contradicts the 500-reference corpus.
