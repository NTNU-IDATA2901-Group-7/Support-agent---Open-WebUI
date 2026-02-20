
import requests
import logging

log = logging.getLogger(__name__)

class JiraClient:
    """JIRA integration client"""

    CLOUD_ID = "fdb2f5d2-f08d-4fa1-9916-5593a99e37b3" # Found using https://driwno.atlassian.net/_edge/tenant_info
    BASE_URL = f"https://api.atlassian.com/ex/jira/{CLOUD_ID}" # OAuth 2.0 API url

    def __init__(self, access_token):
        """
        Args:
            access_token: User's OAuth access token
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }


    def test_connection(self) -> bool:
        """Test JIRA connection by fetching current user"""
        url = f"{self.BASE_URL}/rest/api/3/myself"
        try:
            r = requests.get(url, headers=self.headers)
            r.raise_for_status() # Checks the HTTP status code: 200-299 OK, 400-599: raises exception
            return True
        except Exception as e:
            log.error(f"JIRA connection failed: {e}")
            return False


    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        priority: str,
        due_date: str | None = None,
        assignee: str | None = None,
        issue_type: str = "Task",
    ) -> dict | None:
        """
        Create a Jira issue in a given project.

        Args:
            project_key (str): The key of the Jira project (e.g., "TEST").
            summary (str): Title/summary of the issue.
            description (str): Plain text description/body of the issue.
            priority (str): Priority level, e.g., "A", "B", or "C".
            due_date (str): Due date for the issue, in YYYY-MM-DD format (default None).
            assignee (str): Account ID to assign the issue to (default None).
            issue_type (str, optional): Type of Jira issue (default "Task").

        Returns:
            The JSON response from Jira API (created issue info), and None if it fails to create the
        issue.
        """
        url = f"{self.BASE_URL}/rest/api/3/issue"

        fields = {
                "project": {"key": project_key},
                "summary": summary,
                "description": JiraClient._description_to_adf(description),
                "priority": {"name": priority},
                "issuetype": {"name": issue_type},
        }

        if due_date:
            fields["duedate"] = due_date
        if assignee:
            fields["assignee"] = {"id": assignee}

        payload = {"fields": fields}

        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()  # raise exception if HTTP status is 4xx/5xx
            log.info(f"Created Jira issue {response.json().get('key')} in project {project_key}")
            return response.json()
        except Exception as e:
            log.error(f"Failed to create Jira issue: {e}")
            return None


    @staticmethod
    def _description_to_adf(description: str) -> dict:
        """Convert plain description text to ADF (Atlassian Document Format) - used by create_issue
        method"""
        return {
            "content": [
            {
              "content": [
                {
                  "text": description,
                  "type": "text"
                }
              ],
              "type": "paragraph"
            }
            ],
            "type": "doc",
            "version": 1
    }





