conda activate moringa-rad

python scripts/fetch_nci.py --config config/analysis.yaml
python scripts/prepare_nci.py --config config/analysis.yaml
python scripts/analyze_nci.py --config config/analysis.yaml
python scripts/audit_nci_raw.py --config config/analysis.yaml
python scripts/prepare_cancer_modeling.py --config config/analysis.yaml
python scripts/train_cancer.py --config config/analysis.yaml

python scripts/train_cancer.py --config config/analysis.yaml --resume