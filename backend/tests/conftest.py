import os

# Tests check numbers from the synthetic demo dataset, whatever backend/.env says.
os.environ["DATA_SOURCE"] = "synthetic"
# Never call the Claude API from tests: an empty key (set before config.py loads backend/.env, which
# doesn't override existing variables) makes Lotse use its keyword rules. Claude paths are mocked.
os.environ["ANTHROPIC_API_KEY"] = ""
