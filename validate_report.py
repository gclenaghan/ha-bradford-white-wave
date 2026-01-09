import json
import sys

def validate_todo_report(filepath="todo_report.json"):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        return False
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format: {e}")
        return False

    if not isinstance(data, list):
        print("Error: Root element must be a JSON array.")
        return False

    # If the list is empty, it's valid (no TODOs found)
    if not data:
        print("Report is empty (valid).")
        return True

    valid = True
    required_fields = {
        "title", "description", "deepLink", "filePath",
        "lineNumber", "confidence", "rationale", "context", "language"
    }

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            print(f"Error: Item at index {index} is not a JSON object.")
            valid = False
            continue

        missing_fields = required_fields - item.keys()
        if missing_fields:
            print(f"Error: Item at index {index} missing fields: {missing_fields}")
            valid = False

        # Validate confidence score
        if "confidence" in item:
            if not isinstance(item["confidence"], int) or not (1 <= item["confidence"] <= 3):
                print(f"Error: Item at index {index} has invalid confidence score: {item.get('confidence')}")
                valid = False

        # Validate types (basic check)
        for field in ["title", "description", "deepLink", "filePath", "rationale", "context", "language"]:
            if field in item and not isinstance(item[field], str):
                 print(f"Error: Item at index {index} field '{field}' is not a string.")
                 valid = False

        if "lineNumber" in item and not isinstance(item["lineNumber"], int):
             print(f"Error: Item at index {index} field 'lineNumber' is not an integer.")
             valid = False

    if valid:
        print("Validation successful!")
    else:
        print("Validation failed with errors.")

    return valid

if __name__ == "__main__":
    if validate_todo_report():
        sys.exit(0)
    else:
        sys.exit(1)
