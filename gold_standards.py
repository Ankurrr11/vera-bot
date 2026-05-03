import os
import re

def get_gold_standard_examples(category_slug: str) -> str:
    """
    Extracts the 'Gold Standard' example for a specific category from the case-studies.md file.
    """
    path = "examples/case-studies.md"
    if not os.path.exists(path):
        return ""
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Simple regex to find the case study for the category
    # Case studies are usually in ## Case Study X — Category / ... format
    # We look for the Category name and grab the 'Composed message' block
    
    cases = re.split(r'## Case Study \d+ — ', content)
    relevant_examples = []
    
    for case in cases:
        if category_slug.lower() in case.lower():
            # Find the message block (triple backticks)
            match = re.search(r'\*\*Composed message\*\*.*?\n```\n(.*?)\n```', case, re.DOTALL)
            if match:
                message = match.group(1).strip()
                # Find the trigger description
                trigger_match = re.search(r'\*\*Trigger\*\*: (.*?)\n', case)
                trigger_desc = trigger_match.group(1).strip() if trigger_match else "Unknown"
                relevant_examples.append(f"TRIGGER: {trigger_desc}\nGOLD STANDARD MESSAGE: \"{message}\"")
    
    return "\n\n".join(relevant_examples[:1]) # Return the best match

if __name__ == "__main__":
    # Test
    print(get_gold_standard_examples("dentists"))
