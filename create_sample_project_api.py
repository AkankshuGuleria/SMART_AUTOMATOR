import json
import urllib.request

url = "http://127.0.0.1:8000/projects"
payload = {
    "name": "sample-project",
    "repo_path": "C:/Users/Developer/projects/sample-project",
    "remote_url": "https://github.com/example/sample-project.git"
}
data_json = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data_json, method='POST')
req.add_header('Content-Type', 'application/json')

try:
    with urllib.request.urlopen(req) as response:
        result = response.read().decode()
        print("API Response:", result)
        # Parse JSON to extract project ID
        import json as json_mod
        response_data = json_mod.loads(result)
        project_id = response_data.get("id")
        if project_id:
            print(f"Created project with UUID: {project_id}")
            # Save UUID to a file for later use
            with open("project_uuid.txt", "w") as f:
                f.write(project_id)
        else:
            print("No project ID found in response")
except Exception as e:
    print("Error creating project:", e)