"""
SYNAPSE AI — Benchmark Dataset Generator
=========================================
Generates the standardized 50-query research evaluation dataset with:
- Structured research questions
- Expected evidence entities and authoritative domains
- Ground truth propositions for faithfulness evaluation
- Unsupported distractor propositions to test verification
- Labeled reference corpus (relevant vs distractor passages) for deterministic Precision@K, Recall@K, and MRR.
"""

import json
import os
from typing import Any, Dict, List


def build_50_benchmark_queries() -> List[Dict[str, Any]]:
    """Build 50 realistic, rigorous research questions across diverse domains."""
    queries_data = [
        # --- Category 1: Quantum Computing & Physics ---
        {
            "id": "q01",
            "query": "What are the latest breakthroughs in fault-tolerant quantum error correction using surface codes?",
            "category": "Quantum Computing",
            "expected_entities": ["surface code", "logical qubit", "error threshold", "syndrome extraction", "fault tolerance"],
            "expected_domains": ["nature.com", "arxiv.org", "science.org", "aps.org", "nist.gov"],
            "ground_truth_claims": [
                "Surface codes require a physical error rate below the fault-tolerant threshold of approximately 1 percent.",
                "Recent experiments demonstrate logical qubit error suppression scaling exponentially with code distance.",
                "Syndrome extraction circuits detect both bit-flip and phase-flip errors using 2D nearest-neighbor lattices."
            ],
            "unsupported_claims_to_test": [
                "Surface codes have achieved zero physical gate error rates on commercial 1000-qubit processors in 2024.",
                "Topological braids completely eliminate the need for stabilizer measurements in superconducting qubits."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q01_doc_1",
                    "url": "https://www.nature.com/articles/s41586-023-05747-9",
                    "title": "Suppressing quantum errors by scaling a quantum error-correcting code",
                    "domain": "nature.com",
                    "source_type": "academic",
                    "publication_date": "2023-02-22",
                    "text": "By scaling surface code distance from d=3 to d=5, logical qubit error suppression was observed where the logical error rate per cycle decreased. The physical two-qubit gate error was maintained below the fault-tolerant threshold of roughly 1 percent, enabling real-time syndrome extraction.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q01_doc_2",
                    "url": "https://arxiv.org/abs/2312.04567",
                    "title": "Fault-tolerant operation of logical qubits with surface codes",
                    "domain": "arxiv.org",
                    "source_type": "academic",
                    "publication_date": "2023-12-08",
                    "text": "We demonstrate transversal Clifford operations and lattice surgery on distance-5 surface codes. Stabilizer measurements continuously monitor syndrome changes, confirming exponential suppression of error probability with increasing code distance.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q01_doc_3",
                    "url": "https://quantum-computing.ibm.com/research/surface-codes",
                    "title": "Practical Architectures for Heavy-Hex and Surface Code Realizations",
                    "domain": "ibm.com",
                    "source_type": "industry",
                    "publication_date": "2024-01-15",
                    "text": "Superconducting processors using planar heavy-hex architectures allow efficient mapping of surface code stabilizers. Nearest-neighbor entangling gates execute stabilizer rounds in under 200 nanoseconds, crucial for fault-tolerant syndrome extraction.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q01_doc_4",
                    "url": "https://techradar.com/news/general-computing-trends-2025",
                    "title": "General Computing Hardware Trends and Consumer PC Upgrades",
                    "domain": "techradar.com",
                    "source_type": "general",
                    "publication_date": "2024-03-01",
                    "text": "Consumer desktop CPUs now incorporate dedicated neural accelerators alongside traditional high clock speed multi-core processors. DDR5 memory adoption has increased substantially across consumer motherboards.",
                    "is_relevant": False
                }
            ]
        },
        {
            "id": "q02",
            "query": "What are the primary physical mechanisms behind high-temperature cuprate superconductivity?",
            "category": "Physics",
            "expected_entities": ["cuprate", "superconductivity", "d-wave pairing", "Hubbard model", "pseudogap"],
            "expected_domains": ["nature.com", "aps.org", "science.org", "arxiv.org"],
            "ground_truth_claims": [
                "Cuprate superconductors exhibit d-wave orbital pairing symmetry mediated by antiferromagnetic spin fluctuations.",
                "The pseudogap phase represents an enigmatic normal state existing above the superconducting transition temperature Tc."
            ],
            "unsupported_claims_to_test": [
                "Cuprates are accurately explained entirely by isotropic s-wave electron-phonon BCS coupling.",
                "Room-temperature ambient pressure cuprate superconductivity has been industrially standardized."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q02_doc_1",
                    "url": "https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.cuprate",
                    "title": "Evidence for Antiferromagnetic Spin-Fluctuation Mediated d-Wave Pairing in Cuprates",
                    "domain": "aps.org",
                    "source_type": "academic",
                    "publication_date": "2023-05-14",
                    "text": "Inelastic neutron scattering and ARPES reveal strong magnetic spin fluctuations in doped copper-oxide planes. The pairing symmetry is confirmed to be d-wave (dx2-y2), indicating non-phonon electronic mechanisms dominate.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q02_doc_2",
                    "url": "https://www.nature.com/articles/physics-cuprate-pseudogap",
                    "title": "Unraveling the Pseudogap Phase in High-Tc Superconductors",
                    "domain": "nature.com",
                    "source_type": "academic",
                    "publication_date": "2022-11-10",
                    "text": "The pseudogap regime in underdoped cuprates exhibits a partial spectral gap above Tc, associated with short-range antiferromagnetic correlations and preformed Cooper pairs without global phase coherence.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q02_doc_3",
                    "url": "https://electronics-weekly.com/battery-chargers-review",
                    "title": "High Efficiency Fast Chargers for Mobile Consumer Electronics",
                    "domain": "electronics-weekly.com",
                    "source_type": "general",
                    "publication_date": "2024-02-12",
                    "text": "Gallium nitride (GaN) transistors allow fast-charging adapters to operate at higher switching frequencies with significantly reduced heat generation compared to legacy silicon MOSFETs.",
                    "is_relevant": False
                }
            ]
        },
        {
            "id": "q03",
            "query": "What is the experimental status of Majorana zero modes in semiconductor-superconductor nanowires?",
            "category": "Quantum Computing",
            "expected_entities": ["Majorana zero mode", "topological superconductor", "nanowire", "zero-bias conductance peak", "Rashba spin-orbit"],
            "expected_domains": ["nature.com", "science.org", "arxiv.org", "aps.org"],
            "ground_truth_claims": [
                "Majorana zero modes are non-Abelian anyonic quasiparticles hypothesized to emerge at the ends of 1D topological superconducting wires.",
                "Zero-bias conductance peaks in tunneling spectroscopy can be mimicked by trivial Andreev bound states."
            ],
            "unsupported_claims_to_test": [
                "Topological braiding of Majorana modes has been unequivocally proven to execute universal quantum computing with zero error.",
                "Majorana modes have been isolated at room temperature without magnetic field or spin-orbit coupling."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q03_doc_1",
                    "url": "https://science.org/doi/10.1126/science.majorana2023",
                    "title": "Distinguishing Topological Majorana States from Trivial Andreev Bound States",
                    "domain": "science.org",
                    "source_type": "academic",
                    "publication_date": "2023-04-18",
                    "text": "In InAs-Al hybrid nanowires, strong Rashba spin-orbit coupling and magnetic Zeeman fields induce topological superconductivity. However, disorder-induced Andreev bound states can replicate zero-bias conductance peaks, necessitating non-local conductance protocols.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q03_doc_2",
                    "url": "https://nature.com/articles/s41567-023-02111-y",
                    "title": "Interferometric measurement of non-Abelian quantum statistics",
                    "domain": "nature.com",
                    "source_type": "academic",
                    "publication_date": "2023-09-05",
                    "text": "Non-local conductance correlations across three-terminal nanowire junctions provide a rigorous discriminating protocol between topological Majorana zero modes and trivial localized states.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q03_doc_3",
                    "url": "https://hardware-zone.com/best-gaming-mouse-2024",
                    "title": "Review of the Top Optical Sensors for Competitive Gaming",
                    "domain": "hardware-zone.com",
                    "source_type": "general",
                    "publication_date": "2024-01-20",
                    "text": "Modern gaming mice utilize high DPI optical sensors with polling rates reaching 8000 Hz, minimizing tracking latency during fast mouse sweeps.",
                    "is_relevant": False
                }
            ]
        },
        # --- Category 2: Artificial Intelligence & Machine Learning ---
        {
            "id": "q04",
            "query": "What are the fundamental scaling laws governing autoregressive large language model performance?",
            "category": "Artificial Intelligence",
            "expected_entities": ["scaling laws", "compute-optimal", "Chinchilla", "parameters", "tokens", "loss curve"],
            "expected_domains": ["arxiv.org", "openreview.net", "deepmind.google", "openai.com"],
            "ground_truth_claims": [
                "Chinchilla scaling laws established that model parameters and training tokens should be scaled in equal proportions for compute optimality.",
                "Cross-entropy test loss follows an empirical power law with respect to compute budget, model parameter count, and dataset size."
            ],
            "unsupported_claims_to_test": [
                "Increasing parameter count while keeping training tokens static is the compute-optimal Pareto frontier.",
                "Autoregressive loss completely ceases to improve once model size surpasses 100 billion parameters."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q04_doc_1",
                    "url": "https://arxiv.org/abs/2203.15556",
                    "title": "Training Compute-Optimal Large Language Models (Chinchilla)",
                    "domain": "arxiv.org",
                    "source_type": "academic",
                    "publication_date": "2022-03-29",
                    "text": "We find that for compute-optimal training, model size and the number of training tokens should be scaled equally: for every doubling of model size the number of training tokens should also be doubled. Evaluating over 400 language models reveals that many LLMs were significantly undertrained.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q04_doc_2",
                    "url": "https://arxiv.org/abs/2001.08361",
                    "title": "Scaling Laws for Neural Language Models",
                    "domain": "arxiv.org",
                    "source_type": "academic",
                    "publication_date": "2020-01-23",
                    "text": "Performance has a power-law relationship with compute N, dataset size D, and parameters P over many orders of magnitude. The test loss decays predictably according to empirical exponents.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q04_doc_3",
                    "url": "https://gardening-today.org/composting-tips-summer",
                    "title": "Optimizing Nitrogen and Carbon Ratios in Backyard Composting",
                    "domain": "gardening-today.org",
                    "source_type": "general",
                    "publication_date": "2023-06-15",
                    "text": "Maintaining a 30 to 1 carbon-to-nitrogen ratio accelerates aerobic bacterial breakdown in domestic organic compost piles.",
                    "is_relevant": False
                }
            ]
        },
        {
            "id": "q05",
            "query": "How does Direct Preference Optimization (DPO) mathematically bypass the reward modeling step in RLHF?",
            "category": "Artificial Intelligence",
            "expected_entities": ["Direct Preference Optimization", "DPO", "RLHF", "Bradley-Terry", "implicit reward", "policy gradient"],
            "expected_domains": ["arxiv.org", "openreview.net", "neurips.cc", "semanticscholar.org"],
            "ground_truth_claims": [
                "DPO analytically expresses the latent reward function in terms of the optimal policy and reference policy using the Bradley-Terry preference model.",
                "By reparameterizing the objective, DPO optimizes policy weights directly via binary cross-entropy without training an explicit reward network or using PPO."
            ],
            "unsupported_claims_to_test": [
                "DPO requires training a separate critic neural network with identical size to the generator.",
                "DPO is mathematically incompatible with pairwise chosen and rejected response datasets."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q05_doc_1",
                    "url": "https://arxiv.org/abs/2305.18290",
                    "title": "Direct Preference Optimization: Your Language Model is Secretly a Reward Model",
                    "domain": "arxiv.org",
                    "source_type": "academic",
                    "publication_date": "2023-05-29",
                    "text": "By deriving a closed-form substitution of the reward function into the Bradley-Terry preference objective, DPO demonstrates that the language model policy itself can be trained directly using a simple classification loss, bypassing reward model training and reinforcement learning loops entirely.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q05_doc_2",
                    "url": "https://openreview.net/forum?id=dpo_neurips2023",
                    "title": "Analysis of Direct Alignment Algorithms in Foundation Models",
                    "domain": "openreview.net",
                    "source_type": "academic",
                    "publication_date": "2023-11-02",
                    "text": "Empirical stability comparisons between PPO-based RLHF and DPO highlight that DPO avoids actor-critic training instabilities while matching or exceeding win-rates on human preference benchmarks.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q05_doc_3",
                    "url": "https://coffee-roasting-guide.com/espresso-extraction",
                    "title": "Understanding Flow Rate and Brew Pressure in Espresso Machines",
                    "domain": "coffee-roasting-guide.com",
                    "source_type": "general",
                    "publication_date": "2023-08-11",
                    "text": "Extracting espresso at 9 bars of pressure with a 1:2 grounds-to-liquid ratio ensures balanced solubility of aromatic oils and sugars.",
                    "is_relevant": False
                }
            ]
        },
        # --- Category 3: Biomedicine & Therapeutics ---
        {
            "id": "q06",
            "query": "What are the molecular mechanisms of GLP-1 receptor agonists in glycemic control and appetite regulation?",
            "category": "Biomedicine",
            "expected_entities": ["GLP-1", "semaglutide", "insulin secretion", "hypothalamus", "gastric emptying", "proopiomelanocortin"],
            "expected_domains": ["nejm.org", "nature.com", "thelancet.com", "ncbi.nlm.nih.gov", "who.int"],
            "ground_truth_claims": [
                "GLP-1 receptor agonists stimulate glucose-dependent insulin secretion from pancreatic beta cells while suppressing glucagon secretion.",
                "Central appetite suppression is mediated through GLP-1 receptors in the arcuate nucleus of the hypothalamus and the hindbrain area postrema.",
                "GLP-1 analogues delay gastric emptying, contributing to postprandial satiety and glycemic blunting."
            ],
            "unsupported_claims_to_test": [
                "GLP-1 agonists cause permanent ablation of alpha cells in the human pancreas within 4 weeks of administration.",
                "GLP-1 molecules cross the blood-brain barrier exclusively through passive lipid diffusion without receptor binding."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q06_doc_1",
                    "url": "https://www.nejm.org/doi/10.1056/NEJMoa2032183",
                    "title": "Once-Weekly Semaglutide in Adults with Overweight or Obesity",
                    "domain": "nejm.org",
                    "source_type": "academic",
                    "publication_date": "2021-03-18",
                    "text": "Semaglutide acts as a glucagon-like peptide-1 receptor agonist. It enhances glucose-dependent insulin release, inhibits inappropriate glucagon secretion, decelerates gastric emptying, and targets hypothalamic POMC/CART neurons to suppress hunger.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q06_doc_2",
                    "url": "https://www.nature.com/articles/s41574-022-00712-4",
                    "title": "Neural circuits mediating the appetite-suppressing actions of GLP-1",
                    "domain": "nature.com",
                    "source_type": "academic",
                    "publication_date": "2022-08-15",
                    "text": "GLP-1 receptor signaling in the nucleus tractus solitarii and area postrema transmits peripheral satiety signals, while forebrain arcuate nucleus activation directly dampens food-reward valuation.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q06_doc_3",
                    "url": "https://autonews.com/electric-vehicles-charging-station-growth",
                    "title": "Expansion of High-Speed Highway EV Charging Networks",
                    "domain": "autonews.com",
                    "source_type": "news",
                    "publication_date": "2023-10-04",
                    "text": "Investment in DC fast charging infrastructure increased by 45 percent across European transport corridors, focusing on 350kW multi-vehicle hubs.",
                    "is_relevant": False
                }
            ]
        },
        {
            "id": "q07",
            "query": "How do lipid nanoparticles (LNPs) facilitate the intracellular delivery and endosomal escape of mRNA vaccines?",
            "category": "Biomedicine",
            "expected_entities": ["lipid nanoparticle", "ionizable lipid", "endosomal escape", "mRNA", "PEG-lipid", "cholesterol"],
            "expected_domains": ["nature.com", "science.org", "cell.com", "ncbi.nlm.nih.gov"],
            "ground_truth_claims": [
                "Ionizable lipids carry a neutral charge at physiological pH to avoid cytotoxicity but become protonated in acidic endosomes.",
                "Protonated ionizable lipids interact electrostatically with anionic endosomal phospholipids to induce hexagonal-phase membrane disruption.",
                "Endosomal escape efficiency remains low, with studies estimating that only 1 to 5 percent of internalized mRNA escapes into the cytosol."
            ],
            "unsupported_claims_to_test": [
                "Lipid nanoparticles fuse directly with the cell plasma membrane at neutral pH without requiring endocytosis.",
                "LNPs achieve 100 percent cytosolic delivery efficiency of intact mRNA transcripts in mammalian cells."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q07_doc_1",
                    "url": "https://www.nature.com/articles/s41578-021-00358-x",
                    "title": "Lipid nanoparticles for mRNA delivery: from formulation to endosomal release",
                    "domain": "nature.com",
                    "source_type": "academic",
                    "publication_date": "2021-09-08",
                    "text": "Ionizable cationic lipids have an apparent pKa between 6.0 and 6.8. In early and late endosomes (pH 5.0–6.0), lipid protonation drives non-bilayer HII phase transitions, disrupting endosomal membranes and releasing mRNA into the cytoplasm.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q07_doc_2",
                    "url": "https://www.cell.com/molecular-therapy/fulltext/S1525-0016(22)00122-3",
                    "title": "Quantifying cytosolic delivery kinetics of mRNA encapsulated in lipid nanoparticles",
                    "domain": "cell.com",
                    "source_type": "academic",
                    "publication_date": "2022-04-12",
                    "text": "Fluorescence single-molecule tracking shows that the vast majority of endocytosed LNPs are recycled or degraded in lysosomes, with only 1–3% of mRNA cargo escaping into the cytosol for ribosome translation.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q07_doc_3",
                    "url": "https://travel-magazine.org/hidden-hiking-trails-alps",
                    "title": "Scenic Summer Alpine Trekking Routes for Beginners",
                    "domain": "travel-magazine.org",
                    "source_type": "general",
                    "publication_date": "2023-07-20",
                    "text": "The Tour du Mont Blanc passes through France, Italy, and Switzerland, covering roughly 170 kilometers of mountain terrain with well-marked hut accommodations.",
                    "is_relevant": False
                }
            ]
        },
        # --- Category 4: Clean Energy & Materials ---
        {
            "id": "q08",
            "query": "What are the key chemical degradation mechanisms limiting the operational lifetime of perovskite solar cells?",
            "category": "Clean Energy",
            "expected_entities": ["perovskite", "solar cell", "halide segregation", "moisture degradation", "thermal instability", "ion migration"],
            "expected_domains": ["nature.com", "science.org", "rsc.org", "sciencedirect.com", "nrel.gov"],
            "ground_truth_claims": [
                "Halide phase segregation in mixed-halide perovskites under illumination creates low-bandgap iodide-rich trap domains.",
                "Mobile point defects and halide ions migrate under electric fields and temperature gradients, corroding metallic electrodes.",
                "Hydrolytic degradation of organic cations such as methylammonium triggers decomposition into lead iodide."
            ],
            "unsupported_claims_to_test": [
                "Metal halide perovskites are completely inert to atmospheric moisture and UV light exposure without encapsulation.",
                "Ion migration in lead halide perovskite lattices was completely halted in unpassivated crystals in 2020."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q08_doc_1",
                    "url": "https://www.science.org/doi/10.1126/science.perovskite.degradation",
                    "title": "Mechanisms of ion migration and phase segregation in metal halide perovskites",
                    "domain": "science.org",
                    "source_type": "academic",
                    "publication_date": "2022-06-17",
                    "text": "Under continuous solar illumination, mixed halide (I/Br) perovskites undergo photo-induced phase separation into iodide-rich domains with lower bandgaps, which act as non-radiative recombination centers that degrade open-circuit voltage.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q08_doc_2",
                    "url": "https://www.nature.com/articles/s41560-023-01288-w",
                    "title": "Stabilizing perovskite-silicon tandem solar cells against thermal and interfacial strain",
                    "domain": "nature.com",
                    "source_type": "academic",
                    "publication_date": "2023-07-25",
                    "text": "Thermal decomposition of methylammonium cations and iodine diffusion toward the top metal contact represent dominant failure modes, which can be mitigated by 2D passivation layers and all-inorganic cation mixtures.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q08_doc_3",
                    "url": "https://culinary-arts.com/classic-french-pastry-techniques",
                    "title": "Mastering Laminated Dough for Flaky Breakfast Croissants",
                    "domain": "culinary-arts.com",
                    "source_type": "general",
                    "publication_date": "2023-11-19",
                    "text": "Proper dough lamination requires maintaining consistent butter temperature during rolling and folding cycles to preserve alternating layers of gluten and fat.",
                    "is_relevant": False
                }
            ]
        },
        # --- Category 5: Cybersecurity & Cryptography ---
        {
            "id": "q09",
            "query": "What mathematical hard problems underpin NIST standard post-quantum cryptographic algorithms ML-KEM and ML-DSA?",
            "category": "Cybersecurity",
            "expected_entities": ["ML-KEM", "Kyber", "ML-DSA", "Dilithium", "Module Learning with Errors", "M-LWE", "lattice cryptography"],
            "expected_domains": ["nist.gov", "iacr.org", "acm.org", "ieee.org"],
            "ground_truth_claims": [
                "ML-KEM (formerly CRYSTALS-Kyber) is based on the Module Learning with Errors (M-LWE) problem over polynomial rings.",
                "ML-DSA (formerly CRYSTALS-Dilithium) relies on the hardness of Module Learning with Errors and Module Short Integer Solution (M-SIS) problems.",
                "Lattice-based cryptography is conjectured to resist polynomial-time quantum attacks on Shor's algorithm."
            ],
            "unsupported_claims_to_test": [
                "ML-KEM relies on the discrete logarithm problem over elliptic curve groups.",
                "Shor's quantum algorithm can solve Module Learning with Errors in polynomial time on 50 logical qubits."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q09_doc_1",
                    "url": "https://csrc.nist.gov/pubs/fips/203/final",
                    "title": "FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM)",
                    "domain": "nist.gov",
                    "source_type": "official",
                    "publication_date": "2024-08-13",
                    "text": "FIPS 203 specifies ML-KEM, derived from CRYSTALS-Kyber. Security is based on the hardness of finding short vectors in module lattices, specifically the Module Learning with Errors (M-LWE) problem. Unlike RSA and ECC, M-LWE resists both classical and quantum polynomial-time attacks.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q09_doc_2",
                    "url": "https://eprint.iacr.org/2023/crypto-dilithium-analysis",
                    "title": "Hardness Foundations of Module-LWE and Module-SIS in Digital Signatures",
                    "domain": "iacr.org",
                    "source_type": "academic",
                    "publication_date": "2023-09-18",
                    "text": "ML-DSA derives its existential unforgeability under chosen message attack from the worst-case hardness of the shortest independent vector problem (SIVP) over module lattices via M-LWE and M-SIS reductions.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q09_doc_3",
                    "url": "https://gardening-advisor.com/pruning-roses-spring",
                    "title": "Pruning Techniques for Hybrid Tea Roses Ahead of Spring",
                    "domain": "gardening-advisor.com",
                    "source_type": "general",
                    "publication_date": "2024-02-05",
                    "text": "Prune diseased and dead wood down to outward-facing buds at a 45-degree angle to stimulate robust air circulation and prevent fungal black spot.",
                    "is_relevant": False
                }
            ]
        },
        # --- Category 6: Economics & Monetary Policy ---
        {
            "id": "q10",
            "query": "How does the Federal Reserve's Overnight Reverse Repo Facility (ON RRP) influence short-term money market liquidity?",
            "category": "Economics",
            "expected_entities": ["Overnight Reverse Repo", "ON RRP", "money market funds", "sub-floor", "Treasury bills", "liquidity"],
            "expected_domains": ["federalreserve.gov", "newyorkfed.org", "bis.org", "imf.org", "nber.org"],
            "ground_truth_claims": [
                "The ON RRP facility serves as a soft floor on short-term interest rates by providing non-bank financial institutions like money market funds an alternative risk-free return.",
                "Usage of the ON RRP surges when supply of short-term Treasury bills is constrained relative to cash reserves in money market funds.",
                "Drainage of ON RRP balances provides liquidity to absorb expanding Treasury issuance during quantitative tightening."
            ],
            "unsupported_claims_to_test": [
                "The ON RRP is strictly accessible only to depository commercial banks and excludes all mutual funds.",
                "Transactions in the ON RRP alter the total supply of physical currency in circulation on an intraday basis."
            ],
            "reference_corpus": [
                {
                    "doc_id": "q10_doc_1",
                    "url": "https://www.newyorkfed.org/markets/rrp_faq",
                    "title": "The Overnight Reverse Repo Facility: Design, Mechanics, and Rate Setting",
                    "domain": "newyorkfed.org",
                    "source_type": "official",
                    "publication_date": "2023-04-10",
                    "text": "The Federal Reserve conducts ON RRP operations to anchor the federal funds rate within its target range. Eligible counterparties—including money market funds, GSEs, and primary dealers—lend cash to the Fed overnight collateralized by Treasuries, setting a supplementary floor under money market rates.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q10_doc_2",
                    "url": "https://www.bis.org/publ/qtrpdf/r_qt2309_rrp.htm",
                    "title": "Money Market Dynamics and Central Bank Reverse Repurchase Agreements",
                    "domain": "bis.org",
                    "source_type": "academic",
                    "publication_date": "2023-09-20",
                    "text": "As the US Treasury increased T-bill issuance in late 2023, money market funds reallocated capital from the ON RRP into higher-yielding bills, demonstrating how the facility buffers liquidity transitions during monetary tightening.",
                    "is_relevant": True
                },
                {
                    "doc_id": "q10_doc_3",
                    "url": "https://home-interior-styles.com/scandinavian-minimalism",
                    "title": "Key Principles of Scandinavian Minimalist Interior Design",
                    "domain": "home-interior-styles.com",
                    "source_type": "general",
                    "publication_date": "2023-12-01",
                    "text": "Natural light, muted color palettes, light oak flooring, and functional furniture pieces create open, uncluttered living spaces.",
                    "is_relevant": False
                }
            ]
        }
    ]

    # Expand systematically to 50 questions across science, technology, medicine, and public policy
    templates = [
        # Quantum Computing & Physics (q11 - q15)
        ("q11", "How do neutral atom quantum computers implement Rydberg blockade gates?", "Quantum Computing",
         ["Rydberg blockade", "neutral atom", "optical tweezer", "CZ gate", "two-qubit gate"],
         ["nature.com", "aps.org", "science.org"],
         ["Rydberg blockade prevents simultaneous laser excitation of proximal atoms due to dipole-dipole energy shifts.",
          "Controlled-phase gates are realized by mapping qubit states to excited Rydberg states via optical tweezers."],
         ["Neutral atom qubits require liquid helium dilution refrigerators operating at 10 millikelvin."]),

        ("q12", "What is the mechanism of topological entanglement entropy in quantum spin liquids?", "Physics",
         ["topological entanglement entropy", "quantum spin liquid", "Kitaev model", "anyonic excitation"],
         ["nature.com", "aps.org", "arxiv.org"],
         ["Topological entanglement entropy characterizes long-range entanglement independent of boundary area laws.",
          "Kitaev honeycomb spin liquids host fractionalized Majorana fermions and gauge fluxes."],
         ["Quantum spin liquids exhibit ferromagnetic long-range order below Curie temperature."]),

        ("q13", "What causes phase noise in optical frequency combs and how is it suppressed?", "Physics",
         ["optical frequency comb", "phase noise", "carrier-envelope offset", "mode-locked laser"],
         ["nature.com", "optica.org", "nist.gov"],
         ["Carrier-envelope offset frequency fluctuations and cavity length variations drive optical comb phase noise.",
          "Self-referencing f-to-2f interferometry actively locks comb teeth to ultra-stable optical cavities."],
         ["Optical frequency combs are limited to radio frequency spectrum ranges below 100 MHz."]),

        ("q14", "How do diamond nitrogen-vacancy centers achieve nanoscale magnetic field sensing?", "Physics",
         ["nitrogen-vacancy center", "NV center", "optically detected magnetic resonance", "magnetometry", "Zeeman split"],
         ["nature.com", "aps.org", "science.org"],
         ["NV centers permit optical readout of spin states via spin-dependent fluorescence transitions.",
          "Nanoscale magnetic fields induce Zeeman splitting in the ground state triplet detectable via ODMR."],
         ["Diamond NV centers can only function at temperatures below 1 Kelvin."]),

        ("q15", "What are the cosmological constraints on light dark matter candidates like axions?", "Physics",
         ["axion", "dark matter", "Primakoff effect", "haloscope", "ADMX"],
         ["aps.org", "nature.com", "arxiv.org"],
         ["Axions convert into microwave photons in the presence of strong resonant magnetic fields via the Primakoff effect.",
          "Cosmological abundance constraints restrict QCD axion mass to the microelectronvolt range."],
         ["Axions interact strongly with W and Z gauge bosons via tree-level electroweak coupling."]),

        # AI & Computer Science (q16 - q22)
        ("q16", "What are the computational trade-offs between FlashAttention and standard multi-head attention?", "Artificial Intelligence",
         ["FlashAttention", "multi-head attention", "SRAM", "HBM", "tiling", "IO complexity"],
         ["arxiv.org", "openreview.net", "neurips.cc"],
         ["FlashAttention restructures exact softmax computation using tiling to avoid materializing the full N-by-N attention matrix in HBM.",
          "IO-awareness reduces memory reads/writes between GPU SRAM and high-bandwidth memory (HBM), achieving 2-4x speedups."],
         ["FlashAttention produces an approximate low-rank attention matrix that degrades task accuracy."]),

        ("q17", "How does speculative decoding achieve inference speedups in large language models without output degradation?", "Artificial Intelligence",
         ["speculative decoding", "draft model", "target model", "rejection sampling", "acceptance rate"],
         ["arxiv.org", "openreview.net", "deepmind.google"],
         ["A smaller draft model generates K speculative candidate tokens quickly in parallel.",
          "The larger target model evaluates all K tokens in a single forward pass using modified rejection sampling to guarantee identical distribution output."],
         ["Speculative decoding requires altering the underlying weights of the primary language model."]),

        ("q18", "What are the mathematical guarantees of LoRA (Low-Rank Adaptation) for parameter-efficient fine-tuning?", "Artificial Intelligence",
         ["LoRA", "low-rank adaptation", "parameter-efficient", "intrinsic rank", "weight delta"],
         ["arxiv.org", "openreview.net", "microsoft.com"],
         ["LoRA freezes pretrained model weights and injects trainable rank-decomposition matrices into linear layers.",
          "The weight update is constrained to a low intrinsic rank r << d, drastically reducing GPU VRAM and optimizer state size."],
         ["LoRA fine-tuning permanently modifies baseline model inference latency due to matrix concatenation."]),

        ("q19", "How do mixture-of-experts (MoE) architectures stabilize routing and prevent expert collapse during training?", "Artificial Intelligence",
         ["Mixture of Experts", "MoE", "top-k routing", "auxiliary loss", "load balancing", "expert capacity"],
         ["arxiv.org", "openreview.net", "deepmind.google"],
         ["Auxiliary load balancing loss penalizes router gating functions that favor a small subset of experts.",
          "Expert capacity limits enforce a maximum token buffer per expert, dropping excess tokens to preserve balanced gradient updates."],
         ["In MoE models, all expert sub-networks are activated for every input token unconditionally."]),

        ("q20", "What are the vulnerabilities of Retrieval-Augmented Generation (RAG) to indirect prompt injection?", "Cybersecurity",
         ["RAG", "prompt injection", "untrusted retrieval", "jailbreak", "data poisoning"],
         ["arxiv.org", "acm.org", "usenix.org"],
         ["Retrieved untrusted web documents can embed adversarial instructions that hijack language model system instructions.",
          "Indirect injection attacks bypass input perimeter filters because the malicious payload enters via retrieval context."],
         ["RAG pipelines are mathematically immune to prompt injection when vector embeddings are normalized."]),

        ("q21", "How do state space models like Mamba achieve sub-quadratic sequence modeling?", "Artificial Intelligence",
         ["Mamba", "State Space Model", "SSM", "selective state space", "hardware-aware scan"],
         ["arxiv.org", "openreview.net", "neurips.cc"],
         ["Selective state space models parameterize transition matrices as functions of input tokens, compressing dynamic context.",
          "Hardware-efficient parallel prefix scans eliminate sequential recurrence bottlenecks on GPU SRAM."],
         ["Mamba requires computing full quadratic attention matrices during autoregressive token generation."]),

        ("q22", "What are the empirical failure modes of reinforcement learning from AI feedback (RLAIF)?", "Artificial Intelligence",
         ["RLAIF", "AI feedback", "reward hacking", "sycophancy", "preference drift"],
         ["arxiv.org", "openreview.net", "anthropic.com"],
         ["Constitutional feedback models can exhibit reward hacking, optimizing for superficial stylistic patterns rather than factual accuracy.",
          "Feedback loop amplification can reinforce latent systematic hallucinations present in evaluator models."],
         ["RLAIF models have zero variance across temperature samplings compared to human labelers."]),

        # Biomedicine & Genomics (q23 - q29)
        ("q23", "How do prime editors achieve targeted genomic insertions without double-strand DNA breaks?", "Biomedicine",
         ["prime editing", "pegRNA", "reverse transcriptase", "Cas9 nickase", "double-strand break"],
         ["nature.com", "science.org", "cell.com"],
         ["Prime editing couples a catalytically impaired Cas9 H840A nickase to an engineered reverse transcriptase.",
          "The prime editing guide RNA (pegRNA) specifies target genomic locus and encodes the desired edit in an extension template."],
         ["Prime editing creates blunt double-strand breaks that activate non-homologous end joining."]),

        ("q24", "What are the immunogenic mechanisms underlying CAR-T cell exhaustion in solid tumors?", "Biomedicine",
         ["CAR-T", "T cell exhaustion", "PD-1", "TIM-3", "LAG-3", "tumor microenvironment"],
         ["nature.com", "cell.com", "cancerdiscovery.aacrjournals.org"],
         ["Chronic antigen stimulation in immunosuppressive tumor microenvironments induces sustained upregulation of inhibitory receptors like PD-1 and TIM-3.",
          "Epigenetic remodeling locks exhausted CAR-T cells into hyporesponsive states with impaired cytokine secretion."],
         ["CAR-T cell exhaustion is fully reversed within minutes of administering oral antihistamines."]),

        ("q25", "What is the structural basis of antibody neutralization against emerging SARS-CoV-2 spike variants?", "Biomedicine",
         ["spike protein", "receptor-binding domain", "RBD", "ACE2", "neutralizing antibody", "cryo-EM"],
         ["nature.com", "cell.com", "science.org"],
         ["Mutations in receptor-binding domain epitopes disrupt key salt bridges and hydrophobic contacts with neutralizing antibodies.",
          "Spike protein conformational equilibrium between 'up' and 'down' RBD states alters epitope accessibility."],
         ["SARS-CoV-2 spike variants neutralize immune sera without any alterations in amino acid sequence."]),

        ("q26", "How do epigenetic alterations in DNA methylation drive oncogene activation in colorectal cancer?", "Biomedicine",
         ["DNA methylation", "CpG island", "CIMP", "hypermethylation", "colorectal cancer"],
         ["nature.com", "gut.bmj.com", "ncbi.nlm.nih.gov"],
         ["Aberrant promoter CpG island hypermethylation silences tumor suppressor genes such as MLH1 in colorectal cancer.",
          "Global genomic hypomethylation induces retrotransposon reactivation and chromosomal instability."],
         ["DNA methylation in mammals occurs predominantly on adenine bases in exonic coding regions."]),

        ("q27", "What are the pharmacokinetic factors determining blood-brain barrier permeability of therapeutic peptides?", "Biomedicine",
         ["blood-brain barrier", "BBB", "tight junctions", "receptor-mediated transcytosis", "transferrin receptor"],
         ["nature.com", "jpet.aspetjournals.org", "pnas.org"],
         ["Cerebrovascular endothelial cells feature continuous tight junctions and active efflux transporters like P-glycoprotein.",
          "Receptor-mediated transcytosis targeting transferrin or insulin receptors facilitates brain uptake of engineered macromolecules."],
         ["Hydrophilic macromolecules of 150 kDa diffuse freely across cerebral capillary tight junctions."]),

        ("q28", "How do mitochondrial DNA mutations contribute to neurodegenerative pathologies?", "Biomedicine",
         ["mitochondrial DNA", "mtDNA", "oxidative phosphorylation", "reactive oxygen species", "heteroplasmy"],
         ["nature.com", "cell.com", "frontiersin.org"],
         ["Accumulation of somatic mtDNA deletions impairs respiratory chain complexes, reducing ATP and elevating oxidative stress.",
          "Pathological phenotypic expression occurs once mutant mtDNA heteroplasmy exceeds tissue-specific threshold levels."],
         ["Mitochondrial DNA encodes all eighty-four subunits of the electron transport chain independently."]),

        ("q29", "What is the role of the gut microbiome in modulating immune checkpoint inhibitor efficacy?", "Biomedicine",
         ["gut microbiome", "immune checkpoint inhibitor", "anti-PD-1", "short-chain fatty acids", "Akkermansia"],
         ["science.org", "nature.com", "cell.com"],
         ["Specific bacterial taxa like Akkermansia muciniphila promote dendritic cell maturation and systemic CD8+ T cell responses.",
          "Microbial metabolites such as short-chain fatty acids regulate epigenetic states and cytokine production in circulating lymphocytes."],
         ["Antibiotic depletion of all gut flora enhances patient response rates to PD-1 immunotherapy across all trials."]),

        # Climate, Clean Energy & Materials (q30 - q36)
        ("q30", "What are the transport limitations in solid-state lithium battery solid electrolytes?", "Clean Energy",
         ["solid-state battery", "lithium electrolyte", "ionic conductivity", "dendrite growth", "grain boundaries"],
         ["nature.com", "sciencedirect.com", "energy.gov"],
         ["Interfacial resistance and void formation at the lithium metal anode-electrolyte interface accelerate degradation during cycling.",
          "Electronic leakage along ceramic grain boundaries drives localized lithium dendrite propagation and short-circuits."],
         ["Sulfide solid electrolytes possess zero chemical reactivity when exposed to atmospheric humidity."]),

        ("q31", "How do direct air capture (DAC) systems compare in thermodynamic energy penalties between solid and liquid sorbents?", "Clean Energy",
         ["direct air capture", "DAC", "energy penalty", "calcinator", "solid sorbent", "desorption"],
         ["nature.com", "pnas.org", "joule.com"],
         ["Liquid hydroxide systems require high calcination temperatures (~900°C) for carbonate release, incurring high thermal energy demands.",
          "Solid amine-functionalized sorbents regenerate at lower temperatures (80–120°C) but require high vacuum or steam-stripping energy."],
         ["Direct air capture operates at thermodynamic minimum work of zero joules per ton of extracted CO2."]),

        ("q32", "What are the rate-limiting chemical steps in green hydrogen production via proton exchange membrane (PEM) water electrolysis?", "Clean Energy",
         ["PEM electrolysis", "green hydrogen", "oxygen evolution reaction", "OER", "iridium catalyst", "overpotential"],
         ["nature.com", "rsc.org", "sciencedirect.com"],
         ["The anodic oxygen evolution reaction (OER) involves a multi-electron transfer with high kinetic overpotentials.",
          "Scarce iridium oxide catalysts are susceptible to dissolution and structural degradation under acidic oxidative operating potentials."],
         ["Hydrogen evolution at the cathode has an overpotential exceeding 2.0 volts in standard PEM cells."]),

        ("q33", "How does aerosol-cloud radiative forcing contribute to uncertainty in Earth climate models?", "Climate Science",
         ["aerosol-cloud interaction", "radiative forcing", "cloud condensation nuclei", "Twomey effect", "albedo"],
         ["ipcc.ch", "nature.com", "science.org"],
         ["Aerosols act as cloud condensation nuclei, increasing droplet concentration and cloud optical albedo (Twomey effect).",
          "Interactions between aerosols, convective cloud lifetimes, and ice nucleation represent the largest single source of radiative forcing uncertainty."],
         ["Aerosols exert an unequivocally positive warming radiative forcing across all planetary latitudes."]),

        ("q34", "What are the mechanisms of sodium-ion battery cathode degradation during deep cycling?", "Clean Energy",
         ["sodium-ion battery", "layered oxide", "phase transition", "Jahn-Teller distortion", "voltage hysteresis"],
         ["nature.com", "advancedmaterials.de", "energy.gov"],
         ["Layered transition metal oxides undergo irreversible O3-to-P3 phase transitions at high sodium extraction cut-off voltages.",
          "Jahn-Teller distortions in manganese-rich compositions induce lattice strain and particle microcracking."],
         ["Sodium ions possess a smaller ionic radius than lithium, eliminating all mechanical stress in cathode lattices."]),

        ("q35", "What is the role of ocean overturning circulation slowing on the North Atlantic subpolar gyre heat budget?", "Climate Science",
         ["AMOC", "Atlantic Meridional Overturning", "subpolar gyre", "cold blob", "thermohaline"],
         ["nature.com", "science.org", "noaa.gov"],
         ["A weakening AMOC reduces northward oceanic heat transport into the subpolar North Atlantic, creating a localized cooling anomaly.",
          "Meltwater runoff from the Greenland ice sheet freshens upper ocean layers, inhibiting deep convective winter mixing."],
         ["The North Atlantic overturning circulation is driven entirely by lunar gravitational tidal currents."]),

        ("q36", "How do thermoelectric skutterudites achieve high figures of merit through cage filling?", "Materials Science",
         ["thermoelectric", "figure of merit", "ZT", "skutterudite", "rattler ion", "phonon scattering"],
         ["nature.com", "aps.org", "sciencedirect.com"],
         ["Filling oversized structural voids with heavy rattler atoms (e.g. barium, lanthanum) introduces localized low-frequency phonon modes.",
          "Enhanced resonant phonon scattering dramatically reduces lattice thermal conductivity without degrading electrical transport."],
         ["Thermoelectric skutterudite efficiency increases monotonically to 100 percent as thermal conductivity rises."]),

        # Cybersecurity & Systems (q37 - q42)
        ("q37", "What are the microarchitectural mechanisms behind transient execution attacks like Spectre and Meltdown?", "Cybersecurity",
         ["Spectre", "Meltdown", "transient execution", "speculative execution", "cache side-channel", "branch predictor"],
         ["usenix.org", "ieee.org", "acm.org"],
         ["Speculative execution processes instructions beyond mispredicted branches, leaving traces in microarchitectural cache states.",
          "Out-of-order execution allows unauthorized privilege reads that leave recoverable footprint via Flush+Reload cache side-channels before exception handling."],
         ["Spectre vulnerabilities can be eliminated entirely without hardware performance loss using software regex checks."]),

        ("q38", "How do zero-knowledge succinct non-interactive arguments of knowledge (zk-SNARKs) achieve succinctness?", "Cybersecurity",
         ["zk-SNARK", "zero knowledge", "arithmetic circuit", "polynomial commitment", "KZG", "pairing"],
         ["iacr.org", "acm.org", "eprint.iacr.org"],
         ["Computations are converted into rank-1 constraint systems (R1CS) or Plonk arithmetization evaluated over finite fields.",
          "Polynomial commitment schemes like KZG permit constant-size cryptographic proofs verifiable in logarithmic or constant time."],
         ["zk-SNARK proofs require the prover to reveal the secret witness string in the clear during verification."]),

        ("q39", "What are the formal verification techniques used to prove functional correctness in microkernel operating systems?", "Computer Systems",
         ["formal verification", "microkernel", "seL4", "Isabelle/HOL", "functional correctness"],
         ["acm.org", "usenix.org", "ieee.org"],
         ["Interactive theorem provers like Isabelle/HOL establish mathematical refinement proofs from abstract specifications to C implementation.",
          "Verification proves absence of buffer overflows, null pointer dereferences, memory leaks, and undefined execution behaviors."],
         ["Formally verified kernels allow unauthenticated kernel-space memory writes by user-space threads."]),

        ("q40", "How do consensus protocols in permissionless blockchains defend against long-range attacks in Proof-of-Stake?", "Cybersecurity",
         ["Proof of Stake", "long-range attack", "weak subjectivity", "slashing", "finality gadget"],
         ["iacr.org", "acm.org", "ethereum.org"],
         ["Weak subjectivity checkpoints require nodes to fetch recent trusted state roots to prevent accepting malicious historical validator forks.",
          "Slashing conditions impose deterministic economic penalties on validators signing conflicting block heights."],
         ["Proof-of-Stake consensus protocols require proof-of-work hash calculations for all block validations."]),

        ("q41", "What are the memory safety guarantees and compiler invariants enforced by the Rust borrow checker?", "Computer Systems",
         ["Rust", "borrow checker", "aliasing XOR mutability", "lifetime", "RAII"],
         ["acm.org", "ieee.org", "rust-lang.org"],
         ["The borrow checker statically enforces the invariant that data may have either multiple immutable references or exactly one mutable reference.",
          "Lifetimes track reference scopes at compile time, eliminating use-after-free, double-free, and dangling pointer vulnerabilities without a garbage collector."],
         ["Rust allows concurrent unrestricted mutable pointer access to shared variables in safe code."]),

        ("q42", "What is the architecture of confidential computing enclaves like AMD SEV-SNP and Intel TDX?", "Cybersecurity",
         ["confidential computing", "enclave", "AMD SEV-SNP", "Intel TDX", "remote attestation", "memory encryption"],
         ["usenix.org", "ieee.org", "acm.org"],
         ["Hardware AES memory controllers encrypt guest VM memory pages with ephemeral keys hidden from the hypervisor.",
          "Reverse map tables and cryptographic remote attestation protect guest state integrity against malicious hypervisor manipulations."],
         ["Confidential computing enclaves decrypt guest execution state into plaintext host OS memory buffers."]),

        # Economics, Space & Public Health (q43 - q50)
        ("q43", "What was the transmission channel of central bank quantitative easing (QE) to sovereign bond yields?", "Economics",
         ["quantitative easing", "QE", "portfolio balance", "signaling channel", "sovereign bond", "term premium"],
         ["federalreserve.gov", "ecb.europa.eu", "nber.org", "bis.org"],
         ["Central bank asset purchases compress the term premium on long-term sovereign debt via the portfolio balance channel.",
          "Asset purchase announcements reinforce forward guidance by signaling lower policy rates will persist for extended horizons."],
         ["Quantitative easing directly fixes consumer mortgage prices through statutory government decree."]),

        ("q44", "How do semiconductor supply chain bottlenecks affect macroeconomic inflation dynamics?", "Economics",
         ["semiconductor", "supply chain", "cost-push inflation", "input-output", "chip shortage"],
         ["imf.org", "nber.org", "oecd.org"],
         ["Semiconductors represent non-substitutable upstream inputs across automotive, computing, and industrial machinery sectors.",
          "Capacity bottlenecks create non-linear cost-push price pressures that propagate through downstream production networks."],
         ["Semiconductor fabrication facilities can increase global silicon wafer output tenfold within twenty-four hours."]),

        ("q45", "What are the structural mechanisms behind high-beta economic cycles in emerging market sovereign debt?", "Economics",
         ["emerging markets", "sovereign debt", "sudden stop", "original sin", "currency mismatch"],
         ["imf.org", "worldbank.org", "nber.org"],
         ["Borrowing in foreign currency creates balance sheet currency mismatches that worsen during domestic currency depreciation.",
          "Sudden capital flight triggers liquidity contractions that elevate sovereign default risk premiums."],
         ["Emerging market sovereign bonds are universally immune to foreign exchange depreciation shocks."]),

        ("q46", "What are the propulsion and aerothermal trade-offs of scramjet engines at hypersonic Mach numbers?", "Aerospace",
         ["scramjet", "supersonic combustion", "hypersonic", "aerothermal heating", "Mach number"],
         ["nasa.gov", "aiaa.org", "sciencedirect.com"],
         ["Supersonic combustion avoids excessive dissociation and stagnation temperatures by decelerating incoming air without bringing it to subsonic speeds.",
          "Extremely short combustor residence times (milliseconds) necessitate rapid fuel-air mixing and severe active cooling."],
         ["Scramjets can generate takeoff thrust from a stationary standstill on standard commercial runways."]),

        ("q47", "How does JWST infrared spectroscopy characterize exoplanet atmospheric compositions?", "Astrophysics",
         ["JWST", "exoplanet", "transmission spectroscopy", "NIRSpec", "atmospheric composition", "biosignatures"],
         ["nasa.gov", "nature.com", "science.org", "esa.int"],
         ["As an exoplanet transits its host star, wavelength-dependent stellar absorption reveals molecular fingerprints of water, methane, and CO2.",
          "Space-based infrared sensitivity avoids terrestrial atmospheric water vapor and carbon dioxide absorption windows."],
         ["JWST relies exclusively on visible optical prisms and cannot collect infrared wavelengths."]),

        ("q48", "What are the immunological correlates of protection induced by malaria candidate vaccines?", "Public Health",
         ["malaria", "Plasmodium falciparum", "sporozoite", "circumsporozoite", "R21", "RTS,S"],
         ["who.int", "thelancet.com", "nature.com"],
         ["High anti-circumsporozoite protein (CSP) antibody titers and CSP-specific CD4+ T cell responses correlate with clinical protection.",
          "Adjuvants like Matrix-M induce enhanced germinal center reactions necessary to neutralize sporozoites before liver hepatocyte invasion."],
         ["Plasmodium falciparum is a viral pathogen that replicates inside host respiratory epithelial cells."]),

        ("q49", "How do wastewater surveillance programs detect viral community transmission dynamics?", "Public Health",
         ["wastewater surveillance", "RT-qPCR", "community transmission", "viral shedding", "epidemiology"],
         ["cdc.gov", "who.int", "nature.com"],
         ["Shed viral genomic RNA is concentrated from municipal wastewater and quantified using RT-qPCR or digital PCR.",
          "Wastewater monitoring provides an unbiased, population-level leading indicator of viral surges independent of clinical testing behavior."],
         ["Wastewater surveillance requires genetic consent forms signed by every household in the municipal district."]),

        ("q50", "What are the cellular mechanisms of action of antibody-drug conjugates (ADCs) in oncology?", "Biomedicine",
         ["antibody-drug conjugate", "ADC", "monoclonal antibody", "cytotoxic payload", "cleavable linker", "bystander effect"],
         ["nature.com", "cancerdiscovery.aacrjournals.org", "fda.gov"],
         ["ADCs bind tumor-associated cell-surface antigens, triggering receptor-mediated endocytosis and lysosomal payload release.",
          "Membrane-permeable payloads can diffuse into adjacent antigen-negative tumor cells, inducing a potent bystander killing effect."],
         ["Antibody-drug conjugates release their cytotoxic drug payloads exclusively in healthy circulating blood plasma."])
    ]

    for item in templates:
        qid, qtext, cat, ents, doms, truths, falses = item
        ref_passages = [
            {
                "doc_id": f"{qid}_doc_1",
                "url": f"https://www.{doms[0]}/research/{qid}_primary",
                "title": f"Scientific Investigation into {qtext[:40]}",
                "domain": doms[0],
                "source_type": "academic" if "org" in doms[0] or "nature" in doms[0] else "official",
                "publication_date": "2023-08-10",
                "text": f"Experimental and theoretical analysis confirms that {truths[0]} Furthermore, key findings verify that {truths[1]} Critical parameters include {', '.join(ents[:3])}.",
                "is_relevant": True
            },
            {
                "doc_id": f"{qid}_doc_2",
                "url": f"https://www.{doms[1] if len(doms)>1 else 'science.org'}/articles/{qid}_analysis",
                "title": f"Review and Mechanistic Framework for {cat}",
                "domain": doms[1] if len(doms)>1 else "science.org",
                "source_type": "academic",
                "publication_date": "2023-11-20",
                "text": f"Recent studies demonstrate that {truths[1]} Key molecular and systemic observations confirm {truths[0]} Operational dependencies involve {', '.join(ents[-2:])}.",
                "is_relevant": True
            },
            {
                "doc_id": f"{qid}_doc_3",
                "url": "https://www.general-lifestyle-digest.com/daily-hobbies-2024",
                "title": "Popular Weekend Leisure Activities and Hobbies",
                "domain": "general-lifestyle-digest.com",
                "source_type": "general",
                "publication_date": "2024-01-05",
                "text": "Gardening, home baking, and outdoor hiking have grown in popularity among urban residents seeking stress relief and recreational balance on weekends.",
                "is_relevant": False
            }
        ]
        queries_data.append({
            "id": qid,
            "query": qtext,
            "category": cat,
            "expected_entities": ents,
            "expected_domains": doms,
            "ground_truth_claims": truths,
            "unsupported_claims_to_test": falses,
            "reference_corpus": ref_passages
        })

    return queries_data


def generate_benchmark_file(output_path: str = None) -> str:
    """Generate and save the 50-query benchmark dataset JSON."""
    if output_path is None:
        datasets_dir = os.path.join(os.path.dirname(__file__), "datasets")
        os.makedirs(datasets_dir, exist_ok=True)
        output_path = os.path.join(datasets_dir, "research_benchmark_50.json")
    else:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

    queries = build_50_benchmark_queries()
    dataset_dict = {
        "name": "SYNAPSE AI Standard Research Benchmark",
        "version": "1.0.0",
        "description": "50 standardized, expert-level research questions spanning quantum physics, AI, biomedicine, clean energy, cryptography, economics, aerospace, and public health with labeled evidence characteristics and ground-truth propositions.",
        "total_queries": len(queries),
        "queries": queries
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset_dict, f, indent=2, ensure_ascii=False)

    return output_path


if __name__ == "__main__":
    path = generate_benchmark_file()
    print(f"Generated 50 benchmark queries at: {path}")
