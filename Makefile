.PHONY: fetch-nci

fetch-nci:
	python scripts/fetch_nci.py --config config/analysis.yaml
