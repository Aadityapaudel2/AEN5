# Offline MathJax Bundle

Place MathJax v3 "es5" assets under:

`assets/mathjax/es5/tex-mml-chtml.js`

and the sibling files that script references.

The Qt UI loads MathJax from this local path for offline TeX rendering.
If assets are missing, chat still works but LaTeX remains untypeset.

