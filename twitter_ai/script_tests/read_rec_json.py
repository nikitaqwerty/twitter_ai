import json


# Function to load data and extract screen names
def extract_screen_names(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    screen_names = []
    entries = data["data"]["connect_tab_timeline"]["timeline"]["instructions"][2][
        "entries"
    ]
    for entry in entries:
        items = entry["content"]["items"]
        for item in items:
            screen_name = item["item"]["itemContent"]["user_results"]["result"][
                "legacy"
            ]["screen_name"]
            screen_names.append(screen_name)
    return screen_names


# Paths to the files
file_path1 = '/Users/nikita/projects/expert_ai/data/{"contextualUserId":532561541}/1715529710664315000_ConnectTabTimeline.json'
file_path2 = '/Users/nikita/projects/expert_ai/data/{"contextualUserId":944577488805654500}/1715529710368239000_ConnectTabTimeline.json'  # Update this with the actual path


# Extract screen names from both files
screen_names1 = extract_screen_names(file_path1)
screen_names2 = extract_screen_names(file_path2)

# Print the results
# print("Screen names from file 1:", screen_names1)
# print("Screen names from file 2:", screen_names2)

# Compare the lists
common_screen_names = set(screen_names1) & set(screen_names2)
unique_to_file1 = set(screen_names1) - set(screen_names2)
unique_to_file2 = set(screen_names2) - set(screen_names1)

print("Common screen names:", list(common_screen_names))
print("Unique to file 1:", list(unique_to_file1))
print("Unique to file 2:", list(unique_to_file2))
