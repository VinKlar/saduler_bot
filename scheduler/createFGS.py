
from pathlib import Path
from find_group_shed import FGS

JSON_DIR = Path("scheduler/jsons")

for group in FGS.keys():

    for file_path in JSON_DIR.glob("*.json"):

        filename = file_path.stem

        if group in filename:
            FGS[group] = filename
            break

print(FGS)

