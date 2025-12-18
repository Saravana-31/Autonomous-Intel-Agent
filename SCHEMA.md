"""
SCHEMA REFERENCE - Mandatory Fields
====================================

All extraction responses now include these mandatory field schemas.
Every field falls back to "unknown" if not found in the snapshot.


## COMPANY INFORMATION (Mandatory)

{
  "company_name": "string",           # From metadata or LLM
  "domain": "string",                 # From URL patterns
  "description": "string",            # LLM-synthesized from text
  "industry": "string",               # LLM-classified
  "sub_industry": "string",           # LLM-classified
  "services_offered": ["string"],     # Deterministic + LLM-normalized
  "products_offered": ["string"]      # Deterministic + LLM-normalized
}

Example:
{
  "company_name": "Acme Corporation",
  "domain": "acme.com",
  "description": "Leading provider of innovative software solutions...",
  "industry": "Technology",
  "sub_industry": "Software & Services",
  "services_offered": ["Cloud Consulting", "DevOps Support"],
  "products_offered": ["CloudSync Platform", "DataVault"]
}


## CONTACT INFORMATION (Mandatory)

{
  "email_addresses": ["string"],      # Deterministic (regex)
  "phone_numbers": ["string"],        # Deterministic (regex)
  "physical_address": "string",       # Deterministic (heuristic)
  "city": "string",                   # Deterministic (address parsing)
  "country": "string"                 # Deterministic (country patterns)
}

Example:
{
  "email_addresses": ["info@acme.com", "sales@acme.com"],
  "phone_numbers": ["(415) 555-1234", "(415) 555-5678"],
  "physical_address": "123 Tech Street, Suite 100",
  "city": "San Francisco",
  "country": "United States"
}


## SERVICES (Mandatory)

Array of service/product records:

[
  {
    "domain": "string",               # Associated company domain
    "name": "string",                 # Service or product name (LLM-normalized)
    "type": "service | product"       # Type indicator
  },
  ...
]

Example:
[
  {
    "domain": "acme.com",
    "name": "Cloud Consulting Services",
    "type": "service"
  },
  {
    "domain": "acme.com",
    "name": "CloudSync Platform",
    "type": "product"
  }
]


## PEOPLE INFORMATION (Mandatory)

Array of person records:

[
  {
    "person_name": "string",          # Full name (deterministic)
    "role": "string",                 # Job title (LLM-normalized)
    "associated_company": "string"    # Company domain
  },
  ...
]

Example:
[
  {
    "person_name": "John Smith",
    "role": "Chief Executive Officer",
    "associated_company": "acme.com"
  },
  {
    "person_name": "Jane Doe",
    "role": "Vice President of Engineering",
    "associated_company": "acme.com"
  }
]


## SOCIAL MEDIA (Mandatory)

Array of social media links:

[
  {
    "platform": "string",             # Social platform name (LinkedIn, Twitter, etc.)
    "url": "string"                   # Full URL to profile
  },
  ...
]

Example:
[
  {
    "platform": "LinkedIn",
    "url": "https://www.linkedin.com/company/acme-corp"
  },
  {
    "platform": "Twitter",
    "url": "https://twitter.com/acmecorp"
  },
  {
    "platform": "GitHub",
    "url": "https://github.com/acmecorp"
  }
]


## CERTIFICATIONS (Optional)

Array of certification records:

[
  {
    "certification_name": "string",   # Name of certification
    "issuing_authority": "string"     # Organization that issued it
  },
  ...
]

Example:
[
  {
    "certification_name": "ISO 27001",
    "issuing_authority": "International Organization for Standardization"
  },
  {
    "certification_name": "SOC 2 Type II",
    "issuing_authority": "AICPA"
  }
]


## FULL API RESPONSE

GET /process/{company}

{
  "profile": {
    // Legacy fields (for backward compatibility)
    "company_name": "string",
    "description_short": "string",
    "industry": "string",
    "products_services": ["string"],
    "locations": ["string"],
    "key_people": [...],
    "contact": {...},
    "tech_stack": ["string"],

    // New mandatory fields (v2.0)
    "company_information": {
      "company_name": "string",
      "domain": "string",
      "description": "string",
      "industry": "string",
      "sub_industry": "string",
      "services_offered": ["string"],
      "products_offered": ["string"]
    },
    "contact_information": {
      "email_addresses": ["string"],
      "phone_numbers": ["string"],
      "physical_address": "string",
      "city": "string",
      "country": "string"
    },
    "services": [
      {
        "domain": "string",
        "name": "string",
        "type": "service|product"
      }
    ],
    "people": [
      {
        "person_name": "string",
        "role": "string",
        "associated_company": "string"
      }
    ],
    "social_media": [
      {
        "platform": "string",
        "url": "string"
      }
    ],
    "certifications": [
      {
        "certification_name": "string",
        "issuing_authority": "string"
      }
    ]
  },

  "graph": {
    "nodes": [
      {
        "id": "string",
        "type": "Company|Person|Service|Product|Location",
        "label": "string",
        "properties": {}
      }
    ],
    "edges": [
      {
        "source": "string",
        "target": "string",
        "relationship": "HAS_EMPLOYEE|OFFERS|LOCATED_IN|HAS_CERTIFICATION"
      }
    ]
  },

  "llm_engine_used": "Ollama|Phi-2"  // NEW in v2.0
}


## FALLBACK VALUES

If a field cannot be extracted from the text:

String fields → "unknown"
List fields → [] (empty array)
Objects → All fields set to "unknown"

Example (if no emails found):
{
  "contact_information": {
    "email_addresses": [],              // Empty array
    "phone_numbers": ["(555) 123-4567"],
    "physical_address": "unknown",
    "city": "unknown",
    "country": "unknown"
  }
}


## EXTRACTION CONFIDENCE

Each field is extracted via:

1. Deterministic layer (high confidence):
   - Emails (regex pattern match)
   - Phone numbers (formatted correctly)
   - Social links (full URLs)
   - Addresses (heuristic parsing)
   - Domain names

2. LLM layer (variable confidence):
   - Industry (LLM classification)
   - Description (LLM synthesis)
   - Roles (LLM normalization)
   - Service/product names (LLM normalization)

Fields from layer 1 are typically more reliable.
Fields from layer 2 depend on LLM quality and input text clarity.

Future enhancement: Return per-field confidence scores.


## BACKWARD COMPATIBILITY

Old field names still present for compatibility:
  - company_name → company_information.company_name
  - description_short → company_information.description
  - industry → company_information.industry
  - products_services → company_information.services_offered + products_offered
  - key_people → people (with normalized roles)
  - contact.email → contact_information.email_addresses[0]
  - contact.phone → contact_information.phone_numbers[0]

Use new mandatory fields for new code.
Old fields maintained for legacy integrations.


## EXTRACTION ALGORITHM

For each field:

1. Try deterministic extraction
2. If missing or placeholder, try LLM
3. If LLM fails, return "unknown" (never null/error)
4. Merge results: LLM refines deterministic output
5. Validate: All mandatory fields present before returning

Result: 100% uptime, 100% valid JSON, all fields present.
"""
