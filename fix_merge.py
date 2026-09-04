import re

with open("SESSION-LOG.md", "r") as f:
    text = f.read()

# Replace the conflict markers with just the combined text.
text = re.sub(r'<<<<<<< HEAD\n(.*?)=======\n(.*?)\n>>>>>>> main\n', r'\1\n\2\n', text, flags=re.DOTALL)

with open("SESSION-LOG.md", "w") as f:
    f.write(text)
