#!/usr/bin/env python
"""
MCP Tool: Robot External API Interaction
Integrates with external systems via APIs and uses data for testing or test creation.
"""

import os
import logging
import json
import requests
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
from enum import Enum

from src.config.config import (
    GITHUB_API_TOKEN,
    JIRA_API_TOKEN,
    JIRA_URL,
    JENKINS_URL,
    JENKINS_API_TOKEN,
    ERROR_MESSAGES
)

logger = logging.getLogger('robot_tool.external_api_interaction')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class ApiType(str, Enum):
    """Enum for supported API types."""
    GITHUB = "github"
    JIRA = "jira"
    JENKINS = "jenkins"
    REST = "rest"

class RestMethod(str, Enum):
    """Enum for REST methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

class RobotExternalApiRequest(BaseModel):
    """Request model for robot_external_api_interaction tool."""
    api_type: ApiType = Field(
        ...,
        description="Type of API to interact with: 'github', 'jira', 'jenkins', or 'rest'"
    )
    action: str = Field(
        ...,
        description="Action to perform, depends on api_type"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the API call"
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="Additional headers for REST API calls"
    )
    method: Optional[RestMethod] = Field(
        None,
        description="HTTP method for REST API calls"
    )
    url: Optional[str] = Field(
        None,
        description="URL for REST API calls"
    )
    data: Optional[Dict[str, Any]] = Field(
        None,
        description="Data payload for POST/PUT/PATCH REST API calls"
    )

class RobotExternalApiResponse(BaseModel):
    """Response model for robot_external_api_interaction tool."""
    success: bool = Field(
        ...,
        description="Whether the API interaction was successful"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data returned from the API"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def github_api_interaction(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Interact with GitHub API.
    
    Args:
        action: Action to perform (e.g., 'get_issues', 'create_issue', etc.)
        params: Parameters for the API call
        
    Returns:
        Dictionary with API response data
    """
    if not GITHUB_API_TOKEN:
        return {
            "success": False,
            "data": {},
            "error": ERROR_MESSAGES["api_not_enabled"].format(
                api_name="GitHub",
                env_var="GITHUB_API_TOKEN"
            )
        }
    
    try:
        headers = {
            "Authorization": f"token {GITHUB_API_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        base_url = "https://api.github.com"
        
        if action == "get_issues":
            # Get issues from a repository
            repo = params.get("repo", "")
            if not repo:
                return {"success": False, "data": {}, "error": "Repository name is required"}
            
            state = params.get("state", "open")
            per_page = params.get("per_page", 30)
            page = params.get("page", 1)
            
            url = f"{base_url}/repos/{repo}/issues"
            response = requests.get(
                url,
                headers=headers,
                params={"state": state, "per_page": per_page, "page": page}
            )
            
        elif action == "get_repo":
            # Get repository information
            repo = params.get("repo", "")
            if not repo:
                return {"success": False, "data": {}, "error": "Repository name is required"}
            
            url = f"{base_url}/repos/{repo}"
            response = requests.get(url, headers=headers)
            
        elif action == "create_issue":
            # Create a new issue
            repo = params.get("repo", "")
            if not repo:
                return {"success": False, "data": {}, "error": "Repository name is required"}
            
            title = params.get("title", "")
            body = params.get("body", "")
            
            if not title:
                return {"success": False, "data": {}, "error": "Issue title is required"}
            
            url = f"{base_url}/repos/{repo}/issues"
            data = {
                "title": title,
                "body": body
            }
            
            if "labels" in params:
                data["labels"] = params["labels"]
                
            if "assignees" in params:
                data["assignees"] = params["assignees"]
                
            response = requests.post(url, json=data, headers=headers)
            
        elif action == "get_workflows":
            # Get workflows from a repository
            repo = params.get("repo", "")
            if not repo:
                return {"success": False, "data": {}, "error": "Repository name is required"}
            
            url = f"{base_url}/repos/{repo}/actions/workflows"
            response = requests.get(url, headers=headers)
            
        else:
            return {
                "success": False,
                "data": {},
                "error": f"Unsupported GitHub action: {action}"
            }
        
        # Process response
        if response.status_code >= 200 and response.status_code < 300:
            return {
                "success": True,
                "data": response.json(),
                "error": None
            }
        else:
            return {
                "success": False,
                "data": {},
                "error": f"GitHub API error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        logger.error(f"Error in GitHub API interaction: {e}")
        return {
            "success": False,
            "data": {},
            "error": f"Error in GitHub API interaction: {str(e)}"
        }

def jira_api_interaction(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Interact with Jira API.
    
    Args:
        action: Action to perform (e.g., 'get_issue', 'create_issue', etc.)
        params: Parameters for the API call
        
    Returns:
        Dictionary with API response data
    """
    if not JIRA_API_TOKEN or not JIRA_URL:
        return {
            "success": False,
            "data": {},
            "error": ERROR_MESSAGES["api_not_enabled"].format(
                api_name="Jira",
                env_var="JIRA_API_TOKEN and JIRA_URL"
            )
        }
    
    try:
        # Extract authentication from params or use defaults
        username = params.get("username", "")
        if not username:
            return {"success": False, "data": {}, "error": "Jira username is required"}
        
        auth = (username, JIRA_API_TOKEN)
        headers = {"Content-Type": "application/json"}
        
        if action == "get_issue":
            # Get issue details
            issue_key = params.get("issue_key", "")
            if not issue_key:
                return {"success": False, "data": {}, "error": "Issue key is required"}
            
            url = f"{JIRA_URL}/rest/api/2/issue/{issue_key}"
            response = requests.get(url, auth=auth)
            
        elif action == "create_issue":
            # Create a new issue
            project_key = params.get("project_key", "")
            summary = params.get("summary", "")
            issue_type = params.get("issue_type", "Bug")
            description = params.get("description", "")
            
            if not project_key:
                return {"success": False, "data": {}, "error": "Project key is required"}
            
            if not summary:
                return {"success": False, "data": {}, "error": "Issue summary is required"}
            
            url = f"{JIRA_URL}/rest/api/2/issue"
            data = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "issuetype": {"name": issue_type},
                    "description": description
                }
            }
            
            # Add additional fields if provided
            if "priority" in params:
                data["fields"]["priority"] = {"name": params["priority"]}
                
            response = requests.post(url, json=data, headers=headers, auth=auth)
            
        elif action == "get_projects":
            # Get list of projects
            url = f"{JIRA_URL}/rest/api/2/project"
            response = requests.get(url, auth=auth)
            
        elif action == "search_issues":
            # Search for issues using JQL
            jql = params.get("jql", "")
            max_results = params.get("max_results", 50)
            
            url = f"{JIRA_URL}/rest/api/2/search"
            data = {
                "jql": jql,
                "maxResults": max_results
            }
            
            if "fields" in params:
                data["fields"] = params["fields"]
                
            response = requests.post(url, json=data, headers=headers, auth=auth)
            
        else:
            return {
                "success": False,
                "data": {},
                "error": f"Unsupported Jira action: {action}"
            }
        
        # Process response
        if response.status_code >= 200 and response.status_code < 300:
            return {
                "success": True,
                "data": response.json(),
                "error": None
            }
        else:
            return {
                "success": False,
                "data": {},
                "error": f"Jira API error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        logger.error(f"Error in Jira API interaction: {e}")
        return {
            "success": False,
            "data": {},
            "error": f"Error in Jira API interaction: {str(e)}"
        }

def jenkins_api_interaction(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Interact with Jenkins API.
    
    Args:
        action: Action to perform (e.g., 'get_job', 'build_job', etc.)
        params: Parameters for the API call
        
    Returns:
        Dictionary with API response data
    """
    if not JENKINS_API_TOKEN or not JENKINS_URL:
        return {
            "success": False,
            "data": {},
            "error": ERROR_MESSAGES["api_not_enabled"].format(
                api_name="Jenkins",
                env_var="JENKINS_API_TOKEN and JENKINS_URL"
            )
        }
    
    try:
        # Extract authentication from params or use defaults
        username = params.get("username", "")
        if not username:
            return {"success": False, "data": {}, "error": "Jenkins username is required"}
        
        auth = (username, JENKINS_API_TOKEN)
        
        if action == "get_job":
            # Get job details
            job_name = params.get("job_name", "")
            if not job_name:
                return {"success": False, "data": {}, "error": "Job name is required"}
            
            url = f"{JENKINS_URL}/job/{job_name}/api/json"
            response = requests.get(url, auth=auth)
            
        elif action == "build_job":
            # Trigger a job build
            job_name = params.get("job_name", "")
            if not job_name:
                return {"success": False, "data": {}, "error": "Job name is required"}
            
            url = f"{JENKINS_URL}/job/{job_name}/build"
            response = requests.post(url, auth=auth)
            
            # Jenkins returns 201 Created for successful build requests
            if response.status_code == 201:
                return {
                    "success": True,
                    "data": {"message": f"Build triggered for job {job_name}"},
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "data": {},
                    "error": f"Jenkins API error: {response.status_code} - {response.text}"
                }
            
        elif action == "get_build":
            # Get build details
            job_name = params.get("job_name", "")
            build_number = params.get("build_number", "lastBuild")
            
            if not job_name:
                return {"success": False, "data": {}, "error": "Job name is required"}
            
            url = f"{JENKINS_URL}/job/{job_name}/{build_number}/api/json"
            response = requests.get(url, auth=auth)
            
        elif action == "get_jobs":
            # Get list of jobs
            url = f"{JENKINS_URL}/api/json?tree=jobs[name,url,color]"
            response = requests.get(url, auth=auth)
            
        else:
            return {
                "success": False,
                "data": {},
                "error": f"Unsupported Jenkins action: {action}"
            }
        
        # Process response
        if response.status_code >= 200 and response.status_code < 300:
            return {
                "success": True,
                "data": response.json() if response.content else {"message": "Success"},
                "error": None
            }
        else:
            return {
                "success": False,
                "data": {},
                "error": f"Jenkins API error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        logger.error(f"Error in Jenkins API interaction: {e}")
        return {
            "success": False,
            "data": {},
            "error": f"Error in Jenkins API interaction: {str(e)}"
        }

def rest_api_interaction(
    method: str, 
    url: str, 
    params: Dict[str, Any], 
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Interact with a generic REST API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        url: API endpoint URL
        params: Query parameters
        headers: HTTP headers
        data: Request payload for POST/PUT/PATCH
        
    Returns:
        Dictionary with API response data
    """
    try:
        if not url:
            return {
                "success": False,
                "data": {},
                "error": "URL is required for REST API calls"
            }
        
        headers = headers or {}
        
        # If Content-Type is not specified and we have data, set JSON as default
        if data and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        
        # Make the API call based on the method
        if method == "GET":
            response = requests.get(url, params=params, headers=headers)
        elif method == "POST":
            response = requests.post(url, params=params, headers=headers, json=data)
        elif method == "PUT":
            response = requests.put(url, params=params, headers=headers, json=data)
        elif method == "DELETE":
            response = requests.delete(url, params=params, headers=headers)
        elif method == "PATCH":
            response = requests.patch(url, params=params, headers=headers, json=data)
        else:
            return {
                "success": False,
                "data": {},
                "error": f"Unsupported HTTP method: {method}"
            }
        
        # Try to parse the response as JSON
        try:
            response_data = response.json() if response.content else {}
        except:
            # If not JSON, return the text content
            response_data = {"text": response.text}
        
        # Process response
        if response.status_code >= 200 and response.status_code < 300:
            return {
                "success": True,
                "data": response_data,
                "error": None
            }
        else:
            return {
                "success": False,
                "data": response_data,
                "error": f"REST API error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        logger.error(f"Error in REST API interaction: {e}")
        return {
            "success": False,
            "data": {},
            "error": f"Error in REST API interaction: {str(e)}"
        }

def interact_with_external_api(
    api_type: str,
    action: str,
    params: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    method: Optional[str] = None,
    url: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Interact with external APIs.
    
    Args:
        api_type: Type of API to interact with
        action: Action to perform
        params: Parameters for the API call
        headers: Headers for REST API calls
        method: HTTP method for REST API calls
        url: URL for REST API calls
        data: Data payload for POST/PUT/PATCH REST API calls
        
    Returns:
        Dictionary with API response data
    """
    try:
        if api_type == ApiType.GITHUB:
            return github_api_interaction(action, params)
            
        elif api_type == ApiType.JIRA:
            return jira_api_interaction(action, params)
            
        elif api_type == ApiType.JENKINS:
            return jenkins_api_interaction(action, params)
            
        elif api_type == ApiType.REST:
            if not method:
                return {
                    "success": False, 
                    "data": {}, 
                    "error": "HTTP method is required for REST API calls"
                }
                
            if not url:
                return {
                    "success": False, 
                    "data": {}, 
                    "error": "URL is required for REST API calls"
                }
                
            return rest_api_interaction(method, url, params, headers, data)
            
        else:
            return {
                "success": False,
                "data": {},
                "error": f"Unsupported API type: {api_type}"
            }
            
    except Exception as e:
        logger.error(f"Error in external API interaction: {e}")
        return {
            "success": False,
            "data": {},
            "error": f"Error in external API interaction: {str(e)}"
        }

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_external_api_interaction(request: RobotExternalApiRequest) -> RobotExternalApiResponse:
        """
        Interact with external systems via APIs.
        
        Args:
            request: The request containing API interaction parameters
            
        Returns:
            Response with API data or error
        """
        logger.info(f"Received request for {request.api_type} API interaction: {request.action}")
        
        try:
            result = interact_with_external_api(
                api_type=request.api_type,
                action=request.action,
                params=request.params,
                headers=request.headers,
                method=request.method,
                url=request.url,
                data=request.data
            )
            
            return RobotExternalApiResponse(
                success=result["success"],
                data=result["data"],
                error=result["error"]
            )
            
        except Exception as e:
            error_msg = f"Error in robot_external_api_interaction: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return RobotExternalApiResponse(
                success=False,
                data={},
                error=error_msg
            ) 