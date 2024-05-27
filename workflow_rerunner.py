import requests
import json
import concurrent.futures
import time
import asyncio
from datetime import datetime, timedelta, timezone

async def get_failed_workflows(repo_owner, repo_name):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/runs"
    headers = {
        "Authorization": "token <github personal access token (pat)>"
    }
    params = {
        "per_page": 100,
        "status": "cancelled",  
    }
    try:
        failed_workflows = []
        while url:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for non-200 status codes
            data = response.json()
            print(f"Retrieved {len(data['workflow_runs'])} workflows")
            for run in data["workflow_runs"]:
                if run["conclusion"] == "cancelled":
                    if is_old_and_cannot_rerun(run):
                        print(f"Skipping workflow {run['id']} as it is cancelled and older than 7 days.")
                        continue
                if run["conclusion"] == "failure" or run["conclusion"] == "cancelled":
                    failed_workflows.append(run)
            # Check if there are more pages
            url = response.links.get("next", {}).get("url")  # Get URL of the next page
        # Export JSON response to a file
        with open("failed_workflows.json", "w") as file:
            json.dump(failed_workflows, file, indent=4)
        return failed_workflows
    except requests.HTTPError as e:
        print(f"Failed to retrieve workflows: HTTP error - {e}")
        return []
    except Exception as e:
        print(f"Failed to retrieve workflows: {e}")
        return []

def is_old_and_cannot_rerun(workflow):
    # Get the creation datetime and make it aware of the timezone
    created_at = datetime.fromisoformat(workflow["created_at"].replace("Z", "+00:00"))
    created_at = created_at.replace(tzinfo=timezone.utc)
    
    # Calculate the threshold datetime (7 days ago) and make it aware of the timezone
    threshold = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Check if the workflow is older than 7 days and cannot be rerun
    return created_at < threshold

async def rerun_workflow(repo_owner, repo_name, run_id):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}/rerun"
    headers = {
        "Authorization": "token <github personal access token (pat)>"
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 201:
        print(f"Workflow run {run_id} has been rerun successfully.")
        return True
    else:
        print(f"Failed to rerun workflow run {run_id}.")
        return False

async def check_workflow_status(repo_owner, repo_name, run_id):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
    headers = {
        "Authorization": "token <github personal access token (pat)>"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        status = data["status"]
        conclusion = data["conclusion"]
        print(f"Workflow run {run_id} - Status: {status}, Conclusion: {conclusion}")
        return status, conclusion
    else:
        print(f"Failed to retrieve status for workflow run {run_id}.")
        return None, None

async def trigger_and_monitor_workflows(repo_owner, repo_name):
    failed_workflows = await get_failed_workflows(repo_owner, repo_name)
    if failed_workflows:
        for workflow in failed_workflows:
            run_id = workflow["id"]
            if is_old_and_cannot_rerun(workflow):  # Skip if older than 7 days and cannot be rerun
                print(f"Skipping workflow {run_id} as it is older than 7 days and cannot be rerun.")
                continue
            await rerun_workflow(repo_owner, repo_name, run_id)
            await asyncio.sleep(10)  # Delay before checking status
            status, conclusion = await check_workflow_status(repo_owner, repo_name, run_id)
            while status != "completed":
                await asyncio.sleep(5)  # Check status every 10 seconds
                status, conclusion = await check_workflow_status(repo_owner, repo_name, run_id)
    else:
        print("There are currently no workflows that need to be rerun.")

if __name__ == "__main__":
    repo_owner = "<repo_owner>"
    repo_name = "<repo_name>"
    
    # Run the trigger and monitor function initially
    asyncio.run(trigger_and_monitor_workflows(repo_owner, repo_name))
