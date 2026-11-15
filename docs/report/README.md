# CruxTrap project report (LaTeX)

Source of the B.Tech project report. `main.tex` includes `chapters/*.tex`; figures are in
`figures/` (result plots are copied from `docs/figures/`, screenshots are of the dashboard).

## Before submitting

Everything shown in **red [brackets]** in the PDF must be filled in. The values are set in
the block at the top of `main.tex` (`\supervisor`, `\supervisordesig`, `\coursename`,
`\submissionmonth`; the group members and roll numbers are `\studentA`..`\studentC` and
`\rollA`..`\rollC`) and in the dates on the declaration and certificate pages
(`chapters/00-frontmatter.tex`). Check the title page, declaration and certificate wording
against your department's template, add the DTU logo if required, and verify the reference
details in `refs.bib`.

## Build

With Docker (no local TeX needed), from the repository root:

```bash
docker run --rm -v "$PWD/docs/report:/work" -w /work texlive/texlive:latest-medium \
  latexmk -pdf -interaction=nonstopmode main.tex
```

PowerShell: replace `$PWD` with `${PWD}`. With a local TeX Live or MiKTeX: `latexmk -pdf main.tex`.

After re-running the experiments, refresh the plots with
`cp docs/figures/*.png docs/report/figures/`.
