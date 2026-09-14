import sys
sys.path.insert(0, "/root/fly64")
from plugin import llm_consult
print("transport after env-file load:", llm_consult.GLMConsultant().transport)
