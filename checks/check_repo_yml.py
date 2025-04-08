import os
import strictyaml

ANNOTATION_FILE = ".devrev/repo.yml"

schema = strictyaml.Map({
    "deployable": strictyaml.Bool(),
})

def check_repo_yml():
    if not os.path.exists(ANNOTATION_FILE):
        print(f"Annotation file {ANNOTATION_FILE} does not exist.")
        return False
    
    with open(ANNOTATION_FILE) as f:
        text = f.read()
    
    try:
        # Validate the YAML file against the schema
        strictyaml.load(text, schema)
    except strictyaml.YAMLValidationError as e:
        print(f"Error in {ANNOTATION_FILE}: {e}")
        return False
    return True

if __name__ == "__main__":
    if not check_repo_yml():
        print("Please ensure the .devrev/repo.yml file exists and is valid.")
        exit(1)