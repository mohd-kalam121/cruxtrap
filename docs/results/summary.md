# Phase 5 results (auto-generated)

20 seeds × 20000 episodes, balanced population, γ = 0.9. Values are exact expectations of each run's final greedy policy (mean ± 95% CI over seeds).

| Policy | Return | Commands / session | Intel / session | Attacker time (s) | Agreement with best |
|---|---|---|---|---|---|
| Q-learning | 5.686 ± 0.051 | 4.056 ± 0.034 | 9.91 ± 0.10 | 0.14 ± 0.11 | 0.68 ± 0.03 |
| SARSA | 5.702 ± 0.026 | 4.064 ± 0.018 | 9.93 ± 0.05 | 0.17 ± 0.09 | 0.66 ± 0.04 |
| ε-greedy bandit | 5.503 ± 0.021 | 3.982 ± 0.028 | 9.58 ± 0.03 | 0.00 ± 0.00 | 0.54 ± 0.19 |
| Static (always ALLOW) | 5.542 ± 0.000 | 4.034 ± 0.000 | 9.64 ± 0.00 | 0.00 ± 0.00 | — |
| Random | 1.949 ± 0.000 | 2.015 ± 0.000 | 3.91 ± 0.00 | 7.05 ± 0.00 | — |
| Best observable policy | 5.783 | 4.157 | 10.22 | 0.00 | 1.00 |
| Oracle (type known) | 5.935 | — | — | — | — |

Q-learning > static: one-sample t = 5.88, p = 5.8e-06 (n = 20).
Q-learning vs SARSA: Welch t = -0.57, p = 0.57.
Q-learning reaches 0.60 ± 0.21 of the gain available to the best observable policy.

## Validation (Monte Carlo vs exact, seed-0 Q-learning policy)

Return: exact 5.4643, MC 5.4416 ± 0.0430; commands: exact 3.8986, MC 3.8841 ± 0.0268 (50,000 episodes).

## Step-size ablation (Q-learning, separate seeds)

| Step size | Episodes | Return | Beats static | Share of achievable gain |
|---|---|---|---|---|
| constant α=0.1 | 5,000 | 5.343 ± 0.154 | 2/10 | -82% |
| constant α=0.1 | 20,000 | 5.479 ± 0.150 | 4/10 | -26% |
| αₙ=n^-0.6 | 5,000 | 5.662 ± 0.080 | 9/10 | +50% |
| αₙ=n^-0.6 | 20,000 | 5.618 ± 0.138 | 7/10 | +31% |
| αₙ=n^-0.7 (main) | 5,000 | 5.608 ± 0.155 | 8/10 | +28% |
| αₙ=n^-0.7 (main) | 20,000 | 5.710 ± 0.043 | 10/10 | +70% |
| αₙ=n^-0.85 | 5,000 | 5.610 ± 0.092 | 7/10 | +28% |
| αₙ=n^-0.85 | 20,000 | 5.676 ± 0.067 | 8/10 | +56% |
| αₙ=1/n | 5,000 | 5.513 ± 0.087 | 4/10 | -12% |
| αₙ=1/n | 20,000 | 5.611 ± 0.083 | 6/10 | +29% |

## Sensitivity

| Mix | Objective | Static | Q-learning | Best observable | Oracle | Best-policy changes |
|---|---|---|---|---|---|---|
| balanced | intel | 5.542 | 5.736 ± 0.012 | 5.783 | 5.935 | cred_access|early→FAKE, cred_access|mid→FAKE, cred_access|late→FAKE |
| balanced | attrition | 5.542 | 5.659 ± 0.076 | 5.783 | 5.937 | cred_access|early→FAKE, cred_access|mid→FAKE, cred_access|late→FAKE, cleanup|late→DELAY |
| bot_heavy | intel | 5.133 | 5.159 ± 0.039 | 5.222 | 5.281 | fs_browse|early→FAKE, fs_browse|mid→FAKE, fs_browse|late→FAKE, cred_access|early→FAKE, cred_access|mid→FAKE, cred_access|late→FAKE |
| bot_heavy | attrition | 5.133 | 5.135 ± 0.038 | 5.222 | 5.282 | fs_browse|early→FAKE, fs_browse|mid→FAKE, fs_browse|late→FAKE, cred_access|early→FAKE, cred_access|mid→FAKE, cred_access|late→FAKE |
| human_heavy | intel | 6.273 | 6.600 ± 0.060 | 6.740 | 6.953 | cred_access|early→FAKE, cred_access|mid→FAKE, cred_access|late→FAKE |
| human_heavy | attrition | 6.273 | 6.634 ± 0.055 | 6.740 | 6.957 | cred_access|early→FAKE, cred_access|mid→FAKE, cred_access|late→FAKE, cleanup|late→DELAY |
