# Волна ×6 · 6-D · repo-doctrine#24 — T17 «Манифест свежести: генерится, а не пишется».
# manifest       — пересобрать MANIFEST_SHA256.txt (единственный законный способ его менять);
# manifest-check — гейт CI: пересборка в память + сравнение; устарел или правка руками = красный.
.PHONY: manifest manifest-check

manifest:
	python3 scripts/manifest_check.py build

manifest-check:
	python3 scripts/manifest_check.py check
