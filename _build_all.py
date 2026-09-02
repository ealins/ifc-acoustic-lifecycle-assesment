from pathlib import Path
import sys

basedir = Path('dashboard')

# 1. Create requirements.txt
reqs = '''streamlit>=1.28.0
ifcopenshell>=0.29.0
rdflib>=7.0.0
pandas>=2.0.0
plotly>=5.18.0
graphviz>=0.20.0
trimesh>=4.0.0
python-dotenv>=1.0.0
'''
(basedir / 'requirements.txt').write_text(reqs)
print('created requirements.txt')
