import os
import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, Request
from urllib.parse import urlencode
from models import IntegrationItem  # Assuming you already have the IntegrationItem model

# Load environment variables
load_dotenv()

# HubSpot API Credentials from environment
HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID")
HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI")

# HubSpot OAuth and API URLs
HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_CONTACTS_URL = "https://api.hubapi.com/crm/v3/objects/contacts"
HUBSPOT_COMPANIES_URL = "https://api.hubapi.com/crm/v3/objects/companies"

# In-memory token storage (Replace with Redis/DB for production)
TOKEN_STORAGE = {}

async def authorize_hubspot(user_id: str, org_id: str) -> str:
    """
    Redirects the user to HubSpot's OAuth authorization page.
    """
    params = {
        "client_id": HUBSPOT_CLIENT_ID,
        "redirect_uri": HUBSPOT_REDIRECT_URI,
        "scope": "crm.objects.contacts.read crm.objects.companies.read",
        "response_type": "code",
    }
    return f"{HUBSPOT_AUTH_URL}?{urlencode(params)}"

async def oauth2callback_hubspot(request: Request):
    """
    Handles the OAuth callback, exchanges the code for an access token, and stores credentials.
    """
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")

    data = {
        "grant_type": "authorization_code",
        "client_id": HUBSPOT_CLIENT_ID,
        "client_secret": HUBSPOT_CLIENT_SECRET,
        "redirect_uri": HUBSPOT_REDIRECT_URI,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(HUBSPOT_TOKEN_URL, data=data)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to get access token")
        
        tokens = response.json()
        # Store the tokens in memory (replace with Redis or database)
        TOKEN_STORAGE["hubspot"] = tokens

    return {"message": "HubSpot authentication successful"}

async def get_hubspot_credentials(user_id: str, org_id: str):
    """
    Retrieves stored HubSpot credentials. In production, replace this with a database query.
    """
    credentials = TOKEN_STORAGE.get("hubspot")
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing HubSpot credentials")
    return credentials

async def get_items_hubspot(user_id: str, org_id: str) -> list:
    """
    Fetches HubSpot CRM objects (contacts and companies) and returns a list of IntegrationItem objects.
    """
    credentials = await get_hubspot_credentials(user_id, org_id)
    if not credentials:
        raise HTTPException(status_code=401, detail="HubSpot credentials not found")

    headers = {"Authorization": f"Bearer {credentials['access_token']}"}
    integration_items = []

    async with httpx.AsyncClient() as client:
        # Fetching contacts from HubSpot
        contact_response = await client.get(HUBSPOT_CONTACTS_URL, headers=headers)
        if contact_response.status_code == 200:
            contacts = contact_response.json().get("results", [])
            for contact in contacts:
                # Creating IntegrationItem for contacts
                integration_item = IntegrationItem(
                    id=contact.get("id"),
                    name=f"{contact['properties'].get('firstname', '')} {contact['properties'].get('lastname', '')}",
                    type="contact",
                    email=contact['properties'].get("email"),
                    phone=contact['properties'].get("phone"),
                )
                integration_items.append(integration_item)

        # Fetching companies from HubSpot
        company_response = await client.get(HUBSPOT_COMPANIES_URL, headers=headers)
        if company_response.status_code == 200:
            companies = company_response.json().get("results", [])
            for company in companies:
                # Creating IntegrationItem for companies
                integration_item = IntegrationItem(
                    id=company.get("id"),
                    name=company['properties'].get("name", ""),
                    type="company",
                    website=company['properties'].get("website"),
                    industry=company['properties'].get("industry"),
                )
                integration_items.append(integration_item)

    if not integration_items:
        raise HTTPException(status_code=404, detail="No HubSpot items found")

    return integration_items
